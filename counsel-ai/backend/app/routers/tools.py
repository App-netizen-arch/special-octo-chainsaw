"""Tools router — consent-gated actions + OAuth account connections."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..config import settings
from ..database import get_tool_connection, record_audit, upsert_tool_connection
from ..deps import current_user, require_lawyer
from ..models.db import User
from ..models.schemas import ToolCallRequest, ToolPreview
from ..services.tools_connector import (
    build_preview,
    execute_tool,
    list_tools,
    oauth_exchange_code,
    oauth_start_url,
    _load_tokens,
)

log = logging.getLogger("counsel.tools")
router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolResult(BaseModel):
    successful: bool
    data: dict | None = None
    error: str | None = None


@router.get("", response_model=list[ToolPreview])
async def get_tools(user: User = Depends(current_user)) -> list[ToolPreview]:
    return [ToolPreview(**t) for t in list_tools()]


@router.post("/{slug}/preview")
async def preview(slug: str, raw_input: dict[str, Any],
                  user: User = Depends(require_lawyer)) -> dict:
    try:
        return build_preview(slug, raw_input)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{slug}/execute", response_model=ToolResult)
async def execute(slug: str, req: ToolCallRequest,
                  user: User = Depends(require_lawyer)) -> ToolResult:
    """Only runs external-send tools when confirmed=true (consent modal)."""
    result = execute_tool(slug, req.input, req.confirmed, user_id=user.id)
    return ToolResult(**result)


# ------------------------------------------------------------------ OAuth


class ConnectionStatus(BaseModel):
    provider: str
    mode: str
    connected: bool
    account_email: str = ""
    auth_url: str | None = None


@router.get("/connections/{provider}", response_model=ConnectionStatus)
async def connection_status(provider: str,
                            user: User = Depends(current_user)) -> ConnectionStatus:
    if provider not in ("google", "microsoft"):
        raise HTTPException(404, "unknown provider")
    stored = _load_tokens(provider) is not None
    conn = get_tool_connection(user.id, provider)
    url, _state = (None, None)
    configured = bool(
        settings.google_client_id if provider == "google" else settings.microsoft_client_id
    )
    auth_url = None
    if not stored and configured:
        auth_url, _state = oauth_start_url(provider)
        # state would be verified in a browser-based flow; desktop uses the
        # loopback redirect captured by the backend callback below.
    return ConnectionStatus(
        provider=provider,
        mode="live" if settings.tools_mode == "live" else "simulate",
        connected=stored or (conn or {}).get("status") == "connected",
        account_email=(conn or {}).get("account_email", ""),
        auth_url=auth_url,
    )


@router.post("/connections/{provider}/disconnect")
async def disconnect(provider: str, user: User = Depends(current_user)) -> dict:
    from ..services.tools_connector import KEYRING_SERVICE

    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, f"{provider}-oauth", "")
    except Exception:  # noqa: BLE001
        pass
    upsert_tool_connection(user.id, provider, status="disconnected", account_email="")
    record_audit(user.id, f"tools.{provider}_disconnect")
    return {"ok": True}


@router.get("/oauth/callback")
async def oauth_callback(request: Request, code: str = "", state: str = "",
                         provider: str = "") -> dict:
    """Loopback OAuth landing endpoint. Exchanges the code and stores tokens."""
    provider = provider or request.query_params.get("provider", "google")
    if provider not in ("google", "microsoft"):
        raise HTTPException(400, "unknown provider")
    try:
        result = await oauth_exchange_code(provider, code)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"OAuth exchange failed: {exc}") from exc
    record_audit(None, f"tools.{provider}_oauth_connected")
    return {"ok": True, **result}
