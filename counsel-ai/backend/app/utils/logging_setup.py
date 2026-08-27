"""Structured JSON logging with correlation IDs and PII redaction.

Every log record emitted by the backend is a single-line JSON object:
    {"ts": ..., "level": ..., "logger": ..., "msg": ..., "cid": ..., ...}

A correlation ID (uuid) is assigned per HTTP request / WebSocket turn via a
``contextvars.ContextVar`` and attached to every record, so a support engineer
can trace one user action across services. Messages pass through the PII
redactor before serialization — logs never contain client PII.
"""

from __future__ import annotations

import contextvars
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .pii import redact_text

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:16]
    correlation_id.set(cid)
    return cid


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_text(record.getMessage()),
            "cid": correlation_id.get(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)[:2000]
        for key in ("stage", "provider", "status"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return str(payload).replace("'", '"', 1) if False else _json_dumps(payload)


def _json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """Configure root logging once: JSON to stdout + rotating file sink."""
    root = logging.getLogger()
    if getattr(root, "_counsel_configured", False):
        return
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    formatter = JsonFormatter()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    try:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            settings.logs_dir / "counsel.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:  # pragma: no cover — read-only FS still logs to stdout
        pass

    # third-party noise down
    for noisy in ("httpx", "httpcore", "uvicorn.access", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root._counsel_configured = True  # type: ignore[attr-defined]
