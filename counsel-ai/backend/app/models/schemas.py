"""Pydantic request/response schemas shared by all routers."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Mode = Literal["local", "api", "research", "tools"]


class Source(BaseModel):
    """The single normalized citation schema used across the whole product."""

    title: str = "Untitled source"
    url: str = ""
    snippet: str = ""
    document_name: str = ""  # set for RAG citations
    page: Optional[int] = None
    relevance: float = 0.0
    kind: Literal["web", "document"] = "web"


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    mode: Mode = "local"
    api_key: Optional[str] = None  # forwarded transiently by the client
    document_ids: list[str] = Field(default_factory=list)


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    mode: str
    sources: list[Source] = Field(default_factory=list)
    created_at: float


class DocumentOut(BaseModel):
    id: str
    name: str
    pages: int
    chunks: int
    created_at: float


class DocumentQueryRequest(BaseModel):
    query: str
    document_ids: list[str] = Field(default_factory=list)
    top_k: int = 5


class ToolCallRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False  # must be true after the consent modal


class ToolPreview(BaseModel):
    slug: str
    name: str
    description: str
    requires_external_send: bool = True
    input_schema: dict[str, Any]


class SettingsPatch(BaseModel):
    onboarded: Optional[bool] = None
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    privacy_preference: Optional[str] = None
    domain_whitelist: Optional[list[str]] = None


class HealthOut(BaseModel):
    status: str
    services: dict[str, Any]
