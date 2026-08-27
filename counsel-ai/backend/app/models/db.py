"""SQLAlchemy ORM models — Counsel AI production schema.

Multi-user: every workspace object carries ``user_id`` so conversations,
documents, skills and indices are isolated per account. Firm-wide policy
lives in ``firm_settings`` (admin-controlled). Every external transmission
is recorded in ``audit_logs``.
"""

from __future__ import annotations

import time

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> float:
    return time.time()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    # admin | lawyer | paralegal | readonly
    role: Mapped[str] = mapped_column(String(20), default="lawyer", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    practice_areas_json: Mapped[str] = mapped_column(Text, default="[]")
    jurisdictions_json: Mapped[str] = mapped_column(Text, default="[]")
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    accepted_disclaimer_at: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[float] = mapped_column(Float)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(300), default="New conversation")
    created_at: Mapped[float] = mapped_column(Float, default=now)
    updated_at: Mapped[float] = mapped_column(Float, default=now, index=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user|assistant|system
    content: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), default="local")
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    verification_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(400))
    path: Mapped[str] = mapped_column(String(1000))
    pages: Mapped[int] = mapped_column(Integer, default=0)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # indexing|ready|failed
    created_at: Mapped[float] = mapped_column(Float, default=now)


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("builtin_key", name="uq_skills_builtin_key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    builtin_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    triggers_json: Mapped[str] = mapped_column(Text, default="[]")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    example_output: Mapped[str] = mapped_column(Text, default="")
    doc_type: Mapped[str] = mapped_column(String(60), default="general")
    citation_style: Mapped[str] = mapped_column(String(30), default="bluebook")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    updated_at: Mapped[float] = mapped_column(Float, default=now)


class LegalUpdate(Base):
    __tablename__ = "legal_updates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[float] = mapped_column(Float, default=0.0)
    jurisdiction: Mapped[str] = mapped_column(String(120), default="", index=True)
    doc_type: Mapped[str] = mapped_column(String(60), default="other")
    summary: Mapped[str] = mapped_column(Text, default="")
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    impact_brief: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[float] = mapped_column(Float, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)  # e.g. llm.api_call
    target: Mapped[str] = mapped_column(String(300), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    correlation_id: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[float] = mapped_column(Float, default=now, index=True)


class ResearchCache(Base):
    __tablename__ = "research_cache"

    query_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_text: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    expires_at: Mapped[float] = mapped_column(Float, default=0.0)


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"

    text_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    dim: Mapped[int] = mapped_column(Integer, default=0)
    vector_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class FirmSetting(Base):
    __tablename__ = "firm_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(32), default="")


class ToolConnection(Base):
    __tablename__ = "tool_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_tool_conn_user_provider"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str] = mapped_column(String(40))  # gmail|microsoft
    mode: Mapped[str] = mapped_column(String(20), default="simulate")  # simulate|live
    account_email: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="disconnected")
    created_at: Mapped[float] = mapped_column(Float, default=now)


Index("ix_messages_conv_created", Message.conversation_id, Message.created_at)
