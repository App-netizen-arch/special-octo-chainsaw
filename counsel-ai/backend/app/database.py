"""Database session management.

Uses SQLAlchemy over a SQLCipher-aware connection factory (see
``utils.encryption.db_connect``): when ``sqlcipher3`` is installed the SQLite
file is encrypted at rest with the instance master key; otherwise plain SQLite
is used and the fact is logged once so admins can install SQLCipher.

Sessions are per-request/per-operation; a small helper API exposes typed
queries used by routers and services.
"""

from __future__ import annotations

import logging
import json
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models.db import (
    AuditLog,
    Base,
    Conversation,
    Document,
    EmbeddingCache,
    FirmSetting,
    LegalUpdate,
    Message,
    RefreshToken,
    ResearchCache,
    Skill,
    ToolConnection,
    User,
    now,
)
from .utils.encryption import db_connect, sqlcipher_available

log = logging.getLogger("counsel.db")

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    if not sqlcipher_available() and settings.encrypt_at_rest:
        log.warning(
            "SQLCipher driver not found — the SQLite file is NOT encrypted. "
            "Install sqlcipher3 (or set COUNSEL_ENCRYPT_AT_REST=false to silence). "
            "Uploads and the vector index are still AES-256-GCM encrypted."
        )
    _engine = create_engine(
        "sqlite://",
        creator=lambda: db_connect(settings.db_path),
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):  # pragma: no cover
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error."""
    s = get_session_factory()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    """Create schema when missing. Alembic owns migrations in production;
    create_all keeps first-run installs zero-step (idempotent either way)."""
    Base.metadata.create_all(get_engine())


# ------------------------------------------------------------------ helpers


def scalar_one_or_none(session: Session, stmt):
    return session.execute(stmt).scalar_one_or_none()


# ------------------------------------------------------------------ audit


def record_audit(
    user_id: str | None,
    action: str,
    target: str = "",
    detail: dict[str, Any] | None = None,
    correlation_id: str = "",
) -> None:
    """Persist one audit-trail entry. Never raises into request flow."""
    import json

    from .utils.logging_setup import correlation_id as cid_var

    try:
        with session_scope() as s:
            s.add(
                AuditLog(
                    id=uid(),
                    user_id=user_id,
                    action=action,
                    target=target[:300],
                    detail_json=json.dumps(detail or {}, default=str),
                    correlation_id=correlation_id or cid_var.get(),
                )
            )
    except Exception:  # noqa: BLE001 — audit must never break the request
        log.exception("failed to persist audit entry for %s", action)


def list_audit(limit: int = 200, user_id: str | None = None) -> list[dict[str, Any]]:
    import json

    with session_scope() as s:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        rows = s.execute(stmt).scalars().all()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "action": r.action,
                    "target": r.target,
                    "detail": json.loads(r.detail_json or "{}"),
                    "correlation_id": r.correlation_id,
                    "created_at": r.created_at,
                }
            )
    return out


# ------------------------------------------------------------- conversations


def uid(n: int = 24) -> str:
    import uuid

    return uuid.uuid4().hex[:n]


def create_conversation(user_id: str, title: str = "New conversation") -> dict[str, Any]:
    conv_id = uid(16)
    ts = now()
    with session_scope() as s:
        s.add(
            Conversation(
                id=conv_id, user_id=user_id, title=title[:300], created_at=ts, updated_at=ts
            )
        )
    return {"id": conv_id, "title": title[:300], "user_id": user_id, "created_at": ts, "updated_at": ts}


def list_conversations(user_id: str) -> list[dict[str, Any]]:
    with session_scope() as s:
        rows = s.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(300)
        ).scalars().all()
        return [
            {"id": r.id, "title": r.title, "user_id": r.user_id,
             "created_at": r.created_at, "updated_at": r.updated_at}
            for r in rows
        ]


def get_conversation(conv_id: str, user_id: str) -> Optional[dict[str, Any]]:
    with session_scope() as s:
        r = s.get(Conversation, conv_id)
        if r is None or r.user_id != user_id:
            return None
        return {"id": r.id, "title": r.title, "user_id": r.user_id,
                "created_at": r.created_at, "updated_at": r.updated_at}


def delete_conversation(conv_id: str, user_id: str) -> bool:
    with session_scope() as s:
        r = s.get(Conversation, conv_id)
        if r is None or r.user_id != user_id:
            return False
        for m in s.execute(select(Message).where(Message.conversation_id == conv_id)).scalars():
            s.delete(m)
        s.delete(r)
    return True


def rename_conversation(conv_id: str, user_id: str, title: str) -> bool:
    with session_scope() as s:
        r = s.get(Conversation, conv_id)
        if r is None or r.user_id != user_id:
            return False
        r.title = title[:300]
        r.updated_at = now()
    return True


# ------------------------------------------------------------------ messages


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    mode: str = "local",
    sources: list[dict] | None = None,
    verification: dict | None = None,
) -> dict[str, Any]:
    import json

    msg_id = uid(16)
    ts = now()
    with session_scope() as s:
        s.add(
            Message(
                id=msg_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                mode=mode,
                sources_json=json.dumps(sources or []),
                verification_json=json.dumps(verification) if verification else "",
                created_at=ts,
            )
        )
        conv = s.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = ts
    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "mode": mode,
        "sources": sources or [],
        "verification": verification,
        "created_at": ts,
    }


def get_messages(conversation_id: str) -> list[dict[str, Any]]:
    import json

    with session_scope() as s:
        rows = s.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        ).scalars().all()
        out = []
        for r in rows:
            d = {
                "id": r.id,
                "conversation_id": r.conversation_id,
                "role": r.role,
                "content": r.content,
                "mode": r.mode,
                "sources": json.loads(r.sources_json or "[]"),
                "verification": json.loads(r.verification_json) if r.verification_json else None,
                "created_at": r.created_at,
            }
            out.append(d)
    return out


def history_window(conversation_id: str, limit: int = 12) -> list[dict[str, str]]:
    msgs = get_messages(conversation_id)[-limit:]
    return [{"role": m["role"], "content": m["content"]} for m in msgs]


# ----------------------------------------------------------------- documents


def add_document(
    user_id: str, name: str, path: str, pages: int, chunks: int, status: str = "ready"
) -> dict[str, Any]:
    doc_id = uid(16)
    with session_scope() as s:
        s.add(
            Document(
                id=doc_id, user_id=user_id, name=name[:400], path=path,
                pages=pages, chunks=chunks, status=status,
            )
        )
    return {"id": doc_id, "name": name, "pages": pages, "chunks": chunks,
            "status": status, "created_at": now(), "user_id": user_id}


def set_document_status(doc_id: str, status: str, pages: int | None = None,
                        chunks: int | None = None) -> None:
    with session_scope() as s:
        d = s.get(Document, doc_id)
        if d:
            d.status = status
            if pages is not None:
                d.pages = pages
            if chunks is not None:
                d.chunks = chunks


def list_documents(user_id: str) -> list[dict[str, Any]]:
    with session_scope() as s:
        rows = s.execute(
            select(Document).where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
        ).scalars().all()
        return [
            {"id": r.id, "name": r.name, "path": r.path, "pages": r.pages,
             "chunks": r.chunks, "status": r.status, "created_at": r.created_at}
            for r in rows
        ]


def get_document(doc_id: str, user_id: str | None = None) -> Optional[dict[str, Any]]:
    with session_scope() as s:
        d = s.get(Document, doc_id)
        if d is None or (user_id and d.user_id != user_id):
            return None
        return {"id": d.id, "name": d.name, "path": d.path, "pages": d.pages,
                "chunks": d.chunks, "status": d.status, "created_at": d.created_at,
                "user_id": d.user_id}


def delete_document(doc_id: str, user_id: str) -> Optional[str]:
    """Delete metadata row; returns the stored path for the caller to wipe."""
    with session_scope() as s:
        d = s.get(Document, doc_id)
        if d is None or d.user_id != user_id:
            return None
        path = d.path
        s.delete(d)
    return path


# ------------------------------------------------------------------- skills


def upsert_skill(data: dict[str, Any]) -> dict[str, Any]:
    data = {k: v for k, v in data.items()
            if k not in ("triggers", "created_at", "updated_at")}
    if "triggers_json" in data and not isinstance(data["triggers_json"], str):
        data["triggers_json"] = json.dumps(data["triggers_json"])
    sid = data.get("id") or uid(16)
    ts = now()
    with session_scope() as s:
        existing = s.get(Skill, sid)
        if existing:
            for k, v in data.items():
                if k != "id" and hasattr(existing, k):
                    setattr(existing, k, v)
            existing.updated_at = ts
        else:
            s.add(Skill(id=sid, created_at=ts, updated_at=ts, **{
                k: v for k, v in data.items() if k != "id"
            }))
    return {"id": sid, **data}


def list_skills(owner_id: str | None = None) -> list[dict[str, Any]]:
    import json

    with session_scope() as s:
        stmt = select(Skill).order_by(Skill.builtin_key.is_not(False), Skill.name)
        rows = s.execute(stmt).scalars().all()
        return [_skill_dict(r) for r in rows if owner_id is None or r.owner_id in (None, owner_id)]


def get_skill(skill_id: str) -> Optional[dict[str, Any]]:
    with session_scope() as s:
        r = s.get(Skill, skill_id)
        return _skill_dict(r) if r else None


def delete_skill(skill_id: str, owner_id: str) -> bool:
    with session_scope() as s:
        r = s.get(Skill, skill_id)
        if r is None or (r.builtin_key and owner_id != r.owner_id):
            # built-ins are immutable; users manage their own copies
            if r is None or r.owner_id != owner_id:
                return False
        s.delete(r)
    return True


def _skill_dict(r: Skill) -> dict[str, Any]:
    import json

    return {
        "id": r.id,
        "owner_id": r.owner_id,
        "builtin_key": r.builtin_key,
        "name": r.name,
        "description": r.description,
        "triggers": json.loads(r.triggers_json or "[]"),
        "system_prompt": r.system_prompt,
        "example_output": r.example_output,
        "doc_type": r.doc_type,
        "citation_style": r.citation_style,
        "enabled": r.enabled,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


# ------------------------------------------------------------ legal updates


def add_legal_update(data: dict[str, Any]) -> bool:
    """Insert unless content_hash already seen (duplicate detection)."""
    with session_scope() as s:
        exists = s.execute(
            select(LegalUpdate).where(LegalUpdate.content_hash == data["content_hash"])
        ).scalar_one_or_none()
        if exists:
            return False
        s.add(LegalUpdate(id=uid(16), **data))
    return True


def list_legal_updates(jurisdiction: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with session_scope() as s:
        stmt = select(LegalUpdate).order_by(LegalUpdate.published_at.desc()).limit(limit)
        if jurisdiction:
            stmt = stmt.where(LegalUpdate.jurisdiction.contains(jurisdiction))
        rows = s.execute(stmt).scalars().all()
        return [
            {
                "id": r.id, "source": r.source, "title": r.title, "url": r.url,
                "published_at": r.published_at, "jurisdiction": r.jurisdiction,
                "doc_type": r.doc_type, "summary": r.summary, "relevance": r.relevance,
                "impact_brief": r.impact_brief, "fetched_at": r.fetched_at,
            }
            for r in rows
        ]


def get_legal_update(update_id: str) -> Optional[dict[str, Any]]:
    with session_scope() as s:
        r = s.get(LegalUpdate, update_id)
        if r is None:
            return None
        return {
            "id": r.id, "source": r.source, "title": r.title, "url": r.url,
            "published_at": r.published_at, "jurisdiction": r.jurisdiction,
            "doc_type": r.doc_type, "summary": r.summary, "relevance": r.relevance,
            "impact_brief": r.impact_brief, "fetched_at": r.fetched_at,
        }


def set_impact_brief(update_id: str, brief: str) -> None:
    with session_scope() as s:
        r = s.get(LegalUpdate, update_id)
        if r:
            r.impact_brief = brief


# ------------------------------------------------------------------- cache


def cache_get(table: type, key_col, key: str, expires_col=None) -> Optional[Any]:
    with session_scope() as s:
        row = s.execute(select(table).where(key_col == key)).scalar_one_or_none()
        if row is None:
            return None
        if expires_col is not None and getattr(row, expires_col) and getattr(row, expires_col) < now():
            return None
        return row


def cache_put(table: type, values: dict[str, Any]) -> None:
    with session_scope() as s:
        s.merge(table(**values))


# ------------------------------------------------------------ firm settings

DEFAULT_FIRM_SETTINGS: dict[str, str] = {
    "allowed_domains_json": "[]",
    "model_policy": "local-first",  # local-only|local-first|api-allowed
    "audit_access_roles": "admin",
    "disclaimer_text": (
        "This tool assists drafting and research; it is not a substitute "
        "for professional legal judgment."
    ),
}


def firm_settings() -> dict[str, str]:
    merged = dict(DEFAULT_FIRM_SETTINGS)
    with session_scope() as s:
        for r in s.execute(select(FirmSetting)).scalars():
            merged[r.key] = r.value
    return merged


def set_firm_setting(key: str, value: str, updated_by: str = "") -> None:
    with session_scope() as s:
        row = s.get(FirmSetting, key)
        if row:
            row.value = value
            row.updated_by = updated_by
        else:
            s.add(FirmSetting(key=key, value=value, updated_by=updated_by))


# --------------------------------------------------------------- tool conns


def upsert_tool_connection(user_id: str, provider: str, **fields: Any) -> dict[str, Any]:
    with session_scope() as s:
        row = s.execute(
            select(ToolConnection).where(
                ToolConnection.user_id == user_id, ToolConnection.provider == provider
            )
        ).scalar_one_or_none()
        if row is None:
            row = ToolConnection(id=uid(16), user_id=user_id, provider=provider)
            s.add(row)
        for k, v in fields.items():
            if hasattr(row, k):
                setattr(row, k, v)
        return {
            "provider": row.provider, "mode": row.mode,
            "status": row.status, "account_email": row.account_email,
        }


def get_tool_connection(user_id: str, provider: str) -> Optional[dict[str, Any]]:
    with session_scope() as s:
        row = s.execute(
            select(ToolConnection).where(
                ToolConnection.user_id == user_id, ToolConnection.provider == provider
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {"provider": row.provider, "mode": row.mode, "status": row.status,
                "account_email": row.account_email}


# ------------------------------------------------------------------ wiping


def wipe_all_data(keep_users: bool = True) -> dict[str, int]:
    """Secure-wipe every table except optionally the users table itself."""
    from .utils.logging_setup import new_correlation_id

    new_correlation_id()
    counts: dict[str, int] = {}
    with session_scope() as s:
        for table in (Message, Conversation, Document, ResearchCache,
                      EmbeddingCache, LegalUpdate, AuditLog, RefreshToken,
                      Skill, ToolConnection, FirmSetting):
            n = s.query(table).delete()
            counts[table.__tablename__] = int(n)
        if not keep_users:
            counts["users"] = int(s.query(User).delete())
    return counts
