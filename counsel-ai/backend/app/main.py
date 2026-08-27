"""Counsel AI backend — single entrypoint (FastAPI production build).

The Flutter desktop app talks ONLY to this process (REST + WebSocket).
Everything else — local LLM, API LLM, research agent, whitelisted search,
RAG, tools connectors, skills engine, legal-update monitor, SQLite + vector
index — lives behind this unified conductor.

Production hardening in this file:

* Structured JSON logging with per-request correlation IDs.
* JWT authentication on every ``/api`` route except login/refresh/health;
  the legacy shared token is accepted ONLY for pre-login health probes.
* Prometheus-compatible ``/metrics`` endpoint.
* Startup: schema init, built-in skill seeding, bootstrap admin, encrypted
  index restore, model-license check, APScheduler start.
* WebSocket chat pipeline: skills auto-injection, hybrid RAG grounding,
  research progress events, multi-agent verification for documents and
  lightweight checks for chat/research answers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import FastAPI, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .auth import decode_access_token, get_user
from .config import settings
from .database import (
    add_message,
    create_conversation,
    get_conversation,
    get_messages,
    history_window,
    init_db,
    record_audit,
)
from .deps import ws_user
from .models.db import User
from .models.schemas import Source
from .routers import admin as admin_router
from .routers import chat as chat_router
from .routers import documents as documents_router
from .routers import research as research_router
from .routers import settings as settings_router
from .routers import skills as skills_router
from .routers import tools as tools_router
from .routers import updates as updates_router
from .routers import users as users_router
from .services.llm import availability, stream_chat, system_prompt
from .services.mdx_generator import TEMPLATES, mdx_document_prompt, render_skeleton
from .services.rag import query_documents, restore_index
from .services.research_agent import stream_research_events
from .services.scheduler import shutdown_scheduler, start_scheduler
from .services.skills_manager import (
    select_relevant_skills,
    seed_builtin_skills,
    skills_to_prompt_blocks,
)
from .utils.citation_normalizer import normalize_all
from .utils.logging_setup import new_correlation_id, setup_logging
from .utils.metrics import inc, observe, render as render_metrics

setup_logging()
log = logging.getLogger("counsel")

app = FastAPI(title="Counsel AI", version="1.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ middleware


PUBLIC_PATHS = {"/api/health", "/api/users/login", "/api/users/refresh",
                "/metrics", "/docs", "/openapi.json"}


@app.middleware("http")
async def correlation_and_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
    cid = new_correlation_id()
    started = time.perf_counter()
    path = request.url.path

    # authentication for API surface (JWT); health stays open for liveness
    if path.startswith("/api") and path not in PUBLIC_PATHS and not _has_valid_jwt(request):
        return JSONResponse({"detail": "Sign in to continue."}, status_code=401)

    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["X-Correlation-ID"] = cid
    inc("http.requests")
    observe("http.latency_seconds", elapsed, {"method": request.method})
    return response


def _has_valid_jwt(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        return False
    payload = decode_access_token(token)
    if payload is None:
        return False
    user = get_user(str(payload["sub"]))
    request.state.user = user
    return user is not None and user.is_active


# ---------------------------------------------------------------------- startup


@app.on_event("startup")
def startup() -> None:
    init_db()
    added = seed_builtin_skills()
    if added:
        log.info("seeded %d built-in skills", added)
    from .auth import bootstrap_admin_if_needed

    bootstrap_admin_if_needed()
    restore_index()

    av = availability()
    if not av.model_path_exists:
        log.warning("No local GGUF model found (LOCAL_MODEL_PATH). Local mode shows guidance.")
    elif av.license and not av.license.get("commercial_ok"):
        log.warning(
            "MODEL LICENSE WARNING: '%s' is licensed '%s'. Commercial use may be "
            "restricted — see docs/LICENSES.md.",
            av.license.get("model"), av.license.get("license"),
        )
    start_scheduler()


@app.on_event("shutdown")
def shutdown() -> None:
    shutdown_scheduler()


# ----------------------------------------------------------------------- health


@app.get("/api/health")
async def health() -> dict[str, Any]:
    av = availability()
    return {
        "status": "ok",
        "version": app.version,
        "services": {
            "database": "ok",
            "local_llm": {
                "available": av.model_path_exists and av.llama_cpp_installed,
                "model_found": av.model_path_exists,
                "llama_cpp_installed": av.llama_cpp_installed,
                "gpu_backend": av.gpu_backend,
                "license_commercial_ok": av.license.get("commercial_ok") if av.license else None,
            },
            "api_llm": {"configured": bool(settings.api_base_url)},
            "search": {
                "provider": settings.search_provider,
                "tavily_key_present": bool(settings.tavily_api_key),
                "searxng_url": settings.searxng_url,
            },
            "scheduler": {"updates_enabled": settings.updates_enabled},
            "tools_mode": settings.tools_mode,
        },
    }


@app.get("/metrics")
async def metrics() -> Response:
    if not settings.metrics_enabled:
        return Response(status_code=404)
    return Response(render_metrics(), media_type="text/plain; charset=utf-8")


# --------------------------------------------------------------------- routers

app.include_router(users_router.router)
app.include_router(chat_router.router)
app.include_router(research_router.router)
app.include_router(documents_router.router)
app.include_router(tools_router.router)
app.include_router(settings_router.router)
app.include_router(skills_router.router)
app.include_router(updates_router.router)
app.include_router(admin_router.router)


# -------------------------------------------------------------------- websocket


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(default="")) -> None:
    user = await ws_user(ws)
    if user is None:
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
                await handle_chat(ws, payload, user)
            elif kind == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        log.info("client disconnected")


def _jurisdiction_for(user: User) -> dict[str, str]:
    import json as _json

    s = _json.loads(user.settings_json or "{}")
    return s


def _policy_blocks_mode(mode: str) -> str | None:
    """Firm model-policy guard. Returns a refusal message or None."""
    policy = _firm_policy()
    if policy == "local-only" and mode != "local":
        return (
            "Your firm's policy restricts this workspace to Local mode "
            "(no external AI calls). Contact your administrator to change it."
        )
    return None


def _firm_policy() -> str:
    from .database import firm_settings

    return firm_settings().get("model_policy", "local-first")


async def handle_chat(ws: WebSocket, p: dict[str, Any], user: User) -> None:
    """One conversational turn: memory, skills injection, streaming, verification."""
    t0 = time.perf_counter()
    new_correlation_id()
    mode: str = p.get("mode", "local")
    message: str = (p.get("message") or "").strip()
    api_key: Optional[str] = p.get("api_key")
    conv_id: Optional[str] = p.get("conversation_id")
    document_ids: list[str] = p.get("document_ids", []) or []
    is_mdx: bool = bool(p.get("mdx"))
    template: str | None = p.get("template")
    run_verification: bool = bool(p.get("verify_document"))

    if not message and template is None:
        await ws.send_json({"type": "error", "message": "Please enter a question first."})
        return

    refusal = _policy_blocks_mode(mode)
    if refusal:
        await ws.send_json({"type": "error", "message": refusal})
        return

    if not conv_id:
        conv = create_conversation(user.id, (message or template)[:60])
        conv_id = conv["id"]
        await ws.send_json({"type": "conversation", "id": conv_id, "title": conv["title"]})
    else:
        conv = get_conversation(conv_id, user.id)
        if conv is None:
            await ws.send_json({"type": "error",
                                "message": "That conversation no longer exists."})
            return

    # template chips render instantly without any model round-trip
    if template in TEMPLATES:
        juris = _jurisdiction_for(user)
        place = ", ".join(filter(None, [juris.get("city"), juris.get("province"),
                                        juris.get("country")]))
        skeleton = render_skeleton(template, place)
        await ws.send_json({"type": "mdx_template", "content": skeleton})
        await ws.send_json({"type": "done"})
        return

    await ws.send_json({"type": "status", "stage": "thinking"})
    if message:
        add_message(conv_id, "user", message, mode)

    # ---- research mode ------------------------------------------------------
    if mode == "research":
        report = ""
        sources: list[dict] = []
        verification: dict | None = None
        async for event in stream_research_events(message, "api", api_key,
                                                  user_id=user.id,
                                                  conversation_id=conv_id):
            etype = event.get("type")
            if etype == "research_progress":
                await ws.send_json(event)
            elif etype == "sources":
                sources = event["sources"]
                await ws.send_json(event)
            elif etype == "verification":
                verification = event["report"]
                await ws.send_json(event)
            elif etype == "token":
                report += event["content"]
                await ws.send_json(event)
            elif etype == "done":
                break
            elif etype == "error":
                await ws.send_json(event)
                return
        saved = add_message(conv_id, "assistant", report, mode, sources, verification)
        await ws.send_json({"type": "done", "message_id": saved["id"]})
        observe("chat.turn_seconds", time.perf_counter() - t0, {"mode": "research"})
        return

    # ---- chat / mdx modes (optionally grounded by RAG) -----------------------
    rag_context = ""
    doc_sources: list[Source] = []
    if document_ids:
        hits = query_documents(message, top_k=5, document_ids=document_ids,
                               user_id=user.id)
        doc_sources = [Source(**h) for h in hits]
        if doc_sources:
            await ws.send_json(
                {"type": "sources", "sources": [s.model_dump() for s in doc_sources]}
            )
            rag_context = "\n\n".join(
                f"[{s.document_name}, Page {s.page}]\n\"{s.snippet}\"" for s in doc_sources
            )

    juris = _jurisdiction_for(user)
    skills = select_relevant_skills(message, mode="drafting" if is_mdx else "chat",
                                    doc_type_hint=None)
    skill_blocks = skills_to_prompt_blocks(skills)
    if skills:
        await ws.send_json({"type": "skills_applied",
                            "skills": [s["name"] for s in skills]})

    if is_mdx:
        instruction = f"Draft this legal document: {message}. Output ONLY the document itself as MDX."
        user_prompt = mdx_document_prompt(instruction, None,
                                          ", ".join(filter(None, [juris.get("city"),
                                                                  juris.get("province"),
                                                                  juris.get("country")])) or
                                          "the applicable jurisdiction",
                                          skill_blocks)
    else:
        user_prompt = message

    messages, _ = chat_router.build_chat_messages(conv_id, user_prompt, mode,
                                                  rag_context, juris, skill_blocks)

    full_text = ""
    async for tok in stream_chat(messages, mode=mode, api_key=api_key,
                                 max_tokens=2048, user_id=user.id):
        full_text += tok
        await ws.send_json({"type": ("mdx_token" if is_mdx else "token"), "content": tok})

    final_sources = [s.model_dump() for s in normalize_all(
        [s.model_dump() for s in doc_sources])]

    verification_payload: dict | None = None
    if full_text.strip():
        if is_mdx and run_verification:
            await ws.send_json({"type": "status", "stage": "verifying"})
            from .services.verification.orchestrator import verify_document

            try:
                verification_payload = await verify_document(
                    full_text,
                    jurisdiction=juris,
                    sources=final_sources,
                    skills=skills,
                    llm_mode=mode,
                    api_key=api_key,
                    user_id=user.id,
                    conversation_id=conv_id,
                )
                await ws.send_json({"type": "verification", "report": verification_payload})
            except Exception as exc:  # noqa: BLE001 — verification must not kill the turn
                log.exception("verification pipeline failed")
                await ws.send_json({"type": "verification_error",
                                    "message": f"Verification could not complete: {exc}"})
        elif not is_mdx and final_sources:
            from .services.verification.orchestrator import verify_light_async

            try:
                verification_payload = await verify_light_async(
                    full_text, final_sources,
                    enabled=settings.verify_source_http,
                    timeout=settings.source_check_timeout,
                )
                await ws.send_json({"type": "verification", "report": verification_payload})
            except Exception:  # noqa: BLE001
                log.exception("light verification failed")

    add_message(conv_id, "assistant", full_text, mode, final_sources, verification_payload)
    await ws.send_json({"type": "done"})
    observe("chat.turn_seconds", time.perf_counter() - t0, {"mode": mode})
