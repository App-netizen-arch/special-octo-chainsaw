"""FastAPI dependencies: current user resolution + role guards.

Access token comes from the ``Authorization: Bearer`` header. The legacy
``X-API-Token`` bootstrap token (single-user installs / health probes) is
still honoured for ``/api/health`` only — see main.py middleware.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, WebSocket, status

from .auth import Role, decode_access_token, get_user, role_at_least
from .models.db import User


def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


async def current_user(request: Request) -> User:
    token = _bearer(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired — sign in again.")
    user = get_user(str(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled.")
    request.state.user = user
    return user


def require_role(minimum: Role):  # noqa: ANN201
    async def guard(user: User = Depends(current_user)) -> User:
        if not role_at_least(user.role, minimum):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({user.role}) does not permit this action.",
            )
        return user

    return guard


# Read-only role may read everything but never mutate; routers use these:
require_lawyer = require_role("lawyer")
require_admin = require_role("admin")


async def ws_user(ws: WebSocket) -> User | None:
    """Authenticate a WebSocket connection via ?token=<access jwt>."""
    token = ws.query_params.get("token", "")
    payload: dict[str, Any] | None = decode_access_token(token)
    if payload is None:
        return None
    user = get_user(str(payload.get("sub", "")))
    return user if user and user.is_active else None
