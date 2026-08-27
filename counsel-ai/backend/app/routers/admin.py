"""Admin router: audit log access, system status, model license info."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth import role_at_least
from ..config import settings
from ..database import firm_settings, list_audit
from ..deps import current_user
from ..models.db import User
from ..services.llm import availability

log = logging.getLogger("counsel.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_audit_access(user: User) -> None:
    allowed_roles = firm_settings().get("audit_access_roles", "admin").split(",")
    allowed_roles = [r.strip() for r in allowed_roles]
    ok = any(role_at_least(user.role, r) for r in allowed_roles)
    if not ok:
        from fastapi import HTTPException

        raise HTTPException(403, "Your role cannot view the audit log.")


@router.get("/audit")
async def audit_log(limit: int = Query(200, le=1000),
                    user_id: str | None = None,
                    user: User = Depends(current_user)) -> list[dict]:
    _require_audit_access(user)
    return list_audit(limit=limit, user_id=user_id)


class SystemStatusOut(BaseModel):
    version: str
    environment: str
    local_llm: dict
    encryption_at_rest: dict
    tools_mode: str
    updates_enabled: bool
    metrics_enabled: bool


@router.get("/status", response_model=SystemStatusOut)
async def system_status(admin: User = Depends(current_user)) -> SystemStatusOut:
    _require_audit_access(admin)
    from ..utils.encryption import sqlcipher_available

    av = availability()
    return SystemStatusOut(
        version="1.0.0",
        environment=settings.environment,
        local_llm={
            "available": av.model_path_exists and av.llama_cpp_installed,
            "model_found": av.model_path_exists,
            "llama_cpp_installed": av.llama_cpp_installed,
            "gpu_backend": av.gpu_backend,
            "license": av.license,
            "blocked_by_license": av.blocked_by_license,
        },
        encryption_at_rest={
            "sqlcipher": sqlcipher_available(),
            "aes_files": settings.encrypt_at_rest,
        },
        tools_mode=settings.tools_mode,
        updates_enabled=settings.updates_enabled,
        metrics_enabled=settings.metrics_enabled,
    )
