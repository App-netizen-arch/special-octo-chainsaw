"""SQLite persistence layer (stdlib sqlite3, WAL mode).

Stores conversations, messages, user settings and document metadata.
Vector data lives in FAISS/numpy index managed by services.rag.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

from .config import settings

_lock = threading.Lock()
_initialized = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New conversation',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'local',
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    pages INTEGER NOT NULL DEFAULT 0,
    chunks INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    global _initialized
    if not _initialized:
        with _lock:
            if not _initialized:
                conn = sqlite3.connect(settings.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(_SCHEMA)
                _initialized = True
                conn.close()
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    get_conn()


# ---------------------------------------------------------------- conversations


def create_conversation(title: str = "New conversation") -> dict[str, Any]:
    conv_id = uuid.uuid4().hex[:12]
    now = time.time()
    with _lock, get_conn() as c:
        c.execute(
            "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (conv_id, title, now, now),
        )
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}


def list_conversations() -> list[dict[str, Any]]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 200"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_conversation(conv_id: str) -> None:
    with _lock, get_conn() as c:
        c.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
        c.execute("DELETE FROM conversations WHERE id=?", (conv_id,))


def rename_conversation(conv_id: str, title: str) -> None:
    with _lock, get_conn() as c:
        c.execute(
            "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
            (title, time.time(), conv_id),
        )


# --------------------------------------------------------------------- messages


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    mode: str = "local",
    sources: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    msg_id = uuid.uuid4().hex[:12]
    now = time.time()
    with _lock, get_conn() as c:
        c.execute(
            "INSERT INTO messages(id,conversation_id,role,content,mode,sources_json,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (msg_id, conversation_id, role, content, mode, json.dumps(sources or []), now),
        )
        c.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id)
        )
    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "mode": mode,
        "sources": sources or [],
        "created_at": now,
    }


def get_messages(conversation_id: str) -> list[dict[str, Any]]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
            (conversation_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d.pop("sources_json") or "[]")
        out.append(d)
    return out


def history_window(conversation_id: str, limit: int = 12) -> list[dict[str, str]]:
    msgs = get_messages(conversation_id)[-limit:]
    return [{"role": m["role"], "content": m["content"]} for m in msgs]


# -------------------------------------------------------------------- documents


def add_document(name: str, path: str, pages: int, chunks: int) -> dict[str, Any]:
    doc_id = uuid.uuid4().hex[:12]
    now = time.time()
    with _lock, get_conn() as c:
        c.execute(
            "INSERT INTO documents(id,name,path,pages,chunks,created_at) VALUES(?,?,?,?,?,?)",
            (doc_id, name, path, pages, chunks, now),
        )
    return {"id": doc_id, "name": name, "pages": pages, "chunks": chunks, "created_at": now}


def list_documents() -> list[dict[str, Any]]:
    with get_conn() as c:
        rows = c.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_document(doc_id: str) -> Optional[dict[str, Any]]:
    with get_conn() as c:
        row = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return dict(row) if row else None


def delete_document(doc_id: str) -> None:
    with _lock, get_conn() as c:
        row = c.execute("SELECT path FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row:
            try:
                from pathlib import Path

                Path(row["path"]).unlink(missing_ok=True)
            except OSError:
                pass
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))


# --------------------------------------------------------------------- settings


_DEFAULT_SETTINGS: dict[str, str] = {
    "onboarded": "false",
    "country": "United States",
    "province": "California",
    "city": "",
    "privacy_preference": "local-first",
    "domain_whitelist_json": "",  # empty => use defaults from utils.domain_whitelist
}


def get_setting(key: str) -> Optional[str]:
    with get_conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else _DEFAULT_SETTINGS.get(key)


def set_setting(key: str, value: str) -> None:
    with _lock, get_conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES(?,?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def all_settings() -> dict[str, str]:
    merged = dict(_DEFAULT_SETTINGS)
    with get_conn() as c:
        for r in c.execute("SELECT key,value FROM settings").fetchall():
            merged[r["key"]] = r["value"]
    return merged
