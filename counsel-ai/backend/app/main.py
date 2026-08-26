"""Counsel AI backend — single entrypoint (FastAPI).

The Flutter desktop app talks ONLY to this process (REST + WebSocket).
Everything else (local LLM, API LLM, research agent, search, tools stub,
SQLite, vector index) lives behind this unified conductor.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import FastAPI, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import add_message, all_settings, create_conversation, get_messages, init_db
from .models.schemas import Source
from .routers import chat as chat_router
from .routers import documents as documents_router
from .routers import research as research_router
from .routers import settings as settings_router
from .routers import tools as tools_router
from .services.llm import availability, complete, stream_chat, system_prompt
from .services.mdx_generator import TEMPLATES, mdx_document_prompt, render_skeleton
from .services.rag import query_documents, restore_index
from .services.research_agent import stream_research_events
from .utils.citation_normalizer import normalize_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("counsel")

app = FastAPI(title="Counsel AI", version="0.1.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ security


def _authorized(token: Optional[str]) -> bool:
    return token == settings.auth_token


@app.middleware("http")
async def token_auth(request, call_next):  # type: ignore[no-untyped-def]
    path = request.url.path
    if path.startswith("/api") and path not in ("/api/health",):
        header = request.headers.get("x-api-token")
        query = request.query_params.get("token")
        if not _authorized(header or query):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.on_event("startup")
def startup() -> None:
    init_db()
    restore_index()
    av = availability()
    if not av.model_path_exists:
        log.warning("No local GGUF model found (LOCAL_MODEL_PATH). Local mode will show guidance.")


# --------------------------------------------------------------------- health


@app.get("/api/health")
async def health() -> dict[str, Any]:
    av = availability()
    return {
        "status": "ok",
        "services": {
            "database": "ok",
            "local_llm": {
                "available": av.model_path_exists and av.llama_cpp_installed,
                "model_found": av.model_path_exists,
                "llama_cpp_installed": av.llama_cpp_installed,
            },
            "api_llm": {"configured": bool(settings.api_base_url)},
            "search": {
                "provider": settings.search_provider,
                "tavily_key_present": bool(settings.tavily_api_key),
                "searxng_url": settings.searxng_url,
            },
        },
        "version": app.version,
    }


app.include_router(chat_router.router)
app.include_router(research_router.router)
app.include_router(documents_router.router)
app.include_router(tools_router.router)
app.include_router(settings_router.router)


# ------------------------------------------------------------------ websocket


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(default="")) -> None:
    if not _authorized(token):
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Malformed message."})
                continue
            kind = payload.get("type", "chat")
            if kind == "chat":
                await handle_chat(ws, payload)
            elif kind == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        log.info("client disconnected")


async def handle_chat(ws: WebSocket, p: dict[str, Any]) -> None:
    """One conversational turn: persists memory, streams tokens + citations."""
    mode: str = p.get("mode", "api")
    message: str = (p.get("message") or "").strip()
    api_key: Optional[str] = p.get("api_key")
    conv_id: Optional[str] = p.get("conversation_id")
    document_ids: list[str] = p.get("document_ids", []) or []
    is_mdx: bool = bool(p.get("mdx"))
    template: str | None = p.get("template")

    if not message:
        await ws.send_json({"type": "error", "message": "Please enter a question first."})
        return

    if not conv_id:
        conv = create_conversation(message[:60])
        conv_id = conv["id"]
        await ws.send_json({"type": "conversation", "id": conv_id, "title": conv["title"]})

    # template chips render instantly without any model round-trip
    if template in TEMPLATES:
        juris = all_settings()
        skeleton = render_skeleton(
            template, f"{juris.get('province', '')}, {juris.get('country', '')}".strip(", ")
        )
        await ws.send_json({"type": "mdx_template", "content": skeleton})
        await ws.send_json({"type": "done"})
        return

    await ws.send_json({"type": "status", "stage": "thinking"})
    add_message(conv_id, "user", message, mode)

    # ---- research mode: dedicated pipeline with progress events -------------
    if mode == "research":
        report = ""
        sources: list[dict] = []
        async for event in stream_research_events(message, "api", api_key):
            etype = event.get("type")
            if etype == "research_progress":
                await ws.send_json(event)
            elif etype == "sources":
                sources = event["sources"]
                await ws.send_json(event)
            elif etype == "token":
                report += event["content"]
                await ws.send_json(event)
            elif etype == "done":
                break
            elif etype == "error":
                await ws.send_json(event)
                return
        saved = add_message(conv_id, "assistant", report, mode, sources)
        await ws.send_json({"type": "done", "message_id": saved["id"]})
        return

    # ---- chat / mdx modes (optionally grounded by RAG) ----------------------
    rag_context = ""
    doc_sources: list[Source] = []
    if document_ids:
        hits = query_documents(message, top_k=5, document_ids=document_ids)
        doc_sources = [Source(**h) for h in hits]
        if doc_sources:
            await ws.send_json(
                {"type": "sources", "sources": [s.model_dump() for s in doc_sources]}
            )
            rag_context = "\n\n".join(
                f"[{s.document_name}, Page {s.page}]\n\"{s.snippet}\"" for s in doc_sources
            )

    if is_mdx:
        instruction = (
            f"Draft this legal document: {message}. "
            "Output ONLY the document itself as MDX."
        )
        user_prompt = mdx_document_prompt(instruction, None, jurisdiction_line())
    else:
        user_prompt = message

    from .routers.chat import build_chat_messages

    messages, _ = build_chat_messages(conv_id, user_prompt, mode, rag_context)

    full_text = ""
    async for tok in stream_chat(messages, mode=mode, api_key=api_key, max_tokens=2048):
        full_text += tok
        await ws.send_json({"type": ("mdx_token" if is_mdx else "token"), "content": tok})

    final_sources = [s.model_dump() for s in normalize_all([s.model_dump() for s in doc_sources])]
    add_message(conv_id, "assistant", full_text, mode, final_sources)
    await ws.send_json({"type": "done"})


def jurisdiction_line() -> str:
    s = all_settings()
    return ", ".join(filter(None, [s.get("city"), s.get("province"), s.get("country")])) or "the applicable jurisdiction"
