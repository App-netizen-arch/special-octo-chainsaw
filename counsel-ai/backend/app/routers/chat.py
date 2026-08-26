"""Chat router: conversations CRUD + non-streaming chat fallback.

Streaming goes through the WebSocket endpoint in main.py; this REST surface
exists for tooling/tests and offline clients.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import (
    add_message,
    create_conversation,
    delete_conversation,
    get_messages,
    history_window,
    list_conversations,
    rename_conversation,
)
from ..models.schemas import ChatRequest, ConversationOut, MessageOut
from ..services.llm import complete, system_prompt
from ..services.rag import query_documents

log = logging.getLogger("counsel.chat")
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/conversations", response_model=ConversationOut)
async def new_conversation(title: str = "New conversation") -> ConversationOut:
    return ConversationOut(**create_conversation(title))


@router.get("/conversations", response_model=list[ConversationOut])
async def get_conversations() -> list[ConversationOut]:
    return [ConversationOut(**c) for c in list_conversations()]


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str) -> dict:
    delete_conversation(conversation_id)
    return {"ok": True}


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(conversation_id: str, title: str) -> ConversationOut:
    rename_conversation(conversation_id, title)
    convs = {c["id"]: c for c in list_conversations()}
    if conversation_id not in convs:
        raise HTTPException(404, "conversation not found")
    return ConversationOut(**convs[conversation_id])


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(conversation_id: str) -> list[MessageOut]:
    msgs = get_messages(conversation_id)
    if not msgs:
        raise HTTPException(404, "conversation not found")
    return [MessageOut(**m) for m in msgs]


class SyncChatResponse(BaseModel):
    reply: str
    sources: list[dict]
    conversation_id: str


@router.post("/chat", response_model=SyncChatResponse)
async def chat(req: ChatRequest) -> SyncChatResponse:
    """Non-streaming variant used by tests and CLI tooling."""
    conv_id = req.conversation_id or create_conversation(req.message[:60])["id"]
    add_message(conv_id, "user", req.message, req.mode)

    context_block = ""
    sources: list[dict] = []
    if req.document_ids:
        hits = query_documents(req.message, top_k=5, document_ids=req.document_ids)
        sources = hits
        if hits:
            context_block = "\n\n".join(
                f"[{h['document_name']}, Page {h['page']}]\n\"{h['snippet']}\"" for h in hits
            )

    from ..database import all_settings

    juris = all_settings()
    system = system_prompt(juris, req.mode)
    user_content = (
        f"{req.message}\n\nUse only these uploaded excerpts when citing:\n{context_block}"
        if context_block
        else req.message
    )
    messages = [{"role": "system", "content": system}] + history_window(conv_id)[
        :-1
    ] + [{"role": "user", "content": user_content}]
    reply = await complete(messages, mode=req.mode if req.mode != "research" else "api")
    add_message(conv_id, "assistant", reply, req.mode, sources)
    return SyncChatResponse(reply=reply, sources=sources, conversation_id=conv_id)


def build_chat_messages(
    conversation_id: Optional[str],
    message: str,
    mode: str,
    rag_context: str = "",
) -> tuple[list[dict], str]:
    """Shared by the WebSocket handler: full message array incl. memory."""
    from ..database import all_settings

    conv_id = conversation_id or ""
    history = history_window(conv_id)[:10] if conv_id else []
    system = system_prompt(all_settings(), mode)
    content = f"{message}\n\nCite only from these uploaded excerpts:\n{rag_context}" if rag_context else message
    return [{"role": "system", "content": system}, *history, {"role": "user", "content": content}], conv_id
