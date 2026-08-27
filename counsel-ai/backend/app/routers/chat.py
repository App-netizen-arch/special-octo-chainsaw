"""Chat router: conversations CRUD + non-streaming chat fallback.

Streaming goes through the WebSocket endpoint in main.py; this REST surface
exists for tooling/tests and offline clients. Skills are selected per query
and injected into the system prompt; only relevant ones, never all.
"""

from __future__ import annotations

import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import (
    add_message,
    create_conversation,
    delete_conversation,
    get_messages,
    get_conversation,
    history_window,
    list_conversations,
    rename_conversation,
)
from ..deps import current_user, require_lawyer
from ..models.db import User
from ..models.schemas import ChatRequest, ConversationOut, MessageOut
from ..services.llm import complete, system_prompt
from ..services.rag import query_documents
from ..services.skills_manager import select_relevant_skills, skills_to_prompt_blocks

log = logging.getLogger("counsel.chat")
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/conversations", response_model=ConversationOut)
async def new_conversation(title: str = "New conversation",
                           user: User = Depends(require_lawyer)) -> ConversationOut:
    return ConversationOut(**create_conversation(user.id, title))


@router.get("/conversations", response_model=list[ConversationOut])
async def get_conversations(user: User = Depends(current_user)) -> list[ConversationOut]:
    return [ConversationOut(**c) for c in list_conversations(user.id)]


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str,
                              user: User = Depends(require_lawyer)) -> dict:
    if not delete_conversation(conversation_id, user.id):
        raise HTTPException(404, "conversation not found")
    return {"ok": True}


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(conversation_id: str, title: str,
                             user: User = Depends(require_lawyer)) -> ConversationOut:
    if not rename_conversation(conversation_id, user.id, title):
        raise HTTPException(404, "conversation not found")
    conv = get_conversation(conversation_id, user.id)
    assert conv is not None
    return ConversationOut(**conv)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(conversation_id: str,
                                    user: User = Depends(current_user)) -> list[MessageOut]:
    conv = get_conversation(conversation_id, user.id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    msgs = get_messages(conversation_id)
    return [MessageOut(**m) for m in msgs]


class SyncChatResponse(BaseModel):
    reply: str
    sources: list[dict]
    conversation_id: str


@router.post("/chat", response_model=SyncChatResponse)
async def chat(req: ChatRequest,
               user: User = Depends(require_lawyer)) -> SyncChatResponse:
    """Non-streaming variant used by tests and CLI tooling."""
    conv_id = req.conversation_id or create_conversation(user.id, req.message[:60])["id"]
    add_message(conv_id, "user", req.message, req.mode)

    context_block = ""
    sources: list[dict] = []
    if req.document_ids:
        hits = query_documents(req.message, top_k=5,
                               document_ids=req.document_ids, user_id=user.id)
        sources = hits
        if hits:
            context_block = "\n\n".join(
                f"[{h['document_name']}, Page {h['page']}]\n\"{h['snippet']}\"" for h in hits
            )

    juris = json.loads(user.settings_json or "{}")
    skills = select_relevant_skills(req.message, mode=req.mode)
    skill_blocks = skills_to_prompt_blocks(skills)
    system = system_prompt(juris, req.mode, skill_blocks=skill_blocks)
    user_content = (
        f"{req.message}\n\nUse only these uploaded excerpts when citing:\n{context_block}"
        if context_block else req.message
    )
    messages = [{"role": "system", "content": system}] + history_window(conv_id)[:-1] + [
        {"role": "user", "content": user_content}
    ]
    reply = await complete(messages, mode=req.mode if req.mode != "research" else "api",
                           api_key=req.api_key, user_id=user.id)
    verification = None
    if req.mode == "research":
        from ..services.research_agent import run_research  # noqa: F401 — parity hook
    add_message(conv_id, "assistant", reply, req.mode, sources, verification)
    return SyncChatResponse(reply=reply, sources=sources, conversation_id=conv_id)


def build_chat_messages(
    conversation_id: Optional[str],
    message: str,
    mode: str,
    rag_context: str = "",
    jurisdiction: dict[str, str] | None = None,
    skill_blocks: list[str] | None = None,
) -> tuple[list[dict], str]:
    """Shared by the WebSocket handler: full message array incl. memory."""
    conv_id = conversation_id or ""
    history = history_window(conv_id)[:10] if conv_id else []
    system = system_prompt(jurisdiction or {}, mode, skill_blocks=skill_blocks)
    content = (
        f"{message}\n\nCite only from these uploaded excerpts:\n{rag_context}"
        if rag_context else message
    )
    return ([{"role": "system", "content": system}, *history,
             {"role": "user", "content": content}], conv_id)
