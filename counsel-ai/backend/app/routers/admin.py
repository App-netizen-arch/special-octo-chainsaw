"""Admin router: user management, audit logs, system stats, model info."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from ..auth import role_at_least, hash_password
from ..config import settings
from ..database import firm_settings, list_audit, session_scope, uid
from ..deps import current_user, require_admin
from ..models.db import User, AuditLog, Conversation, Document, Skill, now
from ..services.llm import availability

log = logging.getLogger("counsel.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_audit_access(user: User) -> None:
    allowed_roles = firm_settings().get("audit_access_roles", "admin").split(",")
    allowed_roles = [r.strip() for r in allowed_roles]
    ok = any(role_at_least(user.role, r) for r in allowed_roles)
    if not ok:
        raise HTTPException(403, "Your role cannot view the audit log.")


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "paralegal"
    full_name: str = ""


class UserUpdate(BaseModel):
    role: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    full_name: str
    is_active: bool
    created_at: str


@router.get("/users", response_model=list[UserOut])
async def list_users(admin: User = Depends(require_admin)):
    """List all users with roles (admin only)."""
    with session_scope() as s:
        users = s.query(User).order_by(User.created_at.desc()).all()
        return [
            UserOut(
                id=u.id,
                email=u.email,
                role=u.role,
                full_name=u.full_name or "",
                is_active=u.is_active,
                created_at=u.created_at.isoformat() if u.created_at else "",
            )
            for u in users
        ]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, admin: User = Depends(require_admin)):
    """Create a new user (admin only)."""
    from sqlalchemy import select
    
    with session_scope() as s:
        existing = s.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(400, "Email already registered")
        
        new_user = User(
            id=uid(16),
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role,
            full_name=data.full_name,
            is_active=True,
        )
        s.add(new_user)
        s.flush()
        
        # Audit log
        s.add(AuditLog(
            id=uid(24),
            user_id=admin.id,
            action="user.create",
            target=new_user.id,
            detail_json=f'{{"email": "{data.email}", "role": "{data.role}"}}',
        ))
        
        return UserOut(
            id=new_user.id,
            email=new_user.email,
            role=new_user.role,
            full_name=new_user.full_name or "",
            is_active=new_user.is_active,
            created_at=new_user.created_at.isoformat() if new_user.created_at else "",
        )


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, data: UserUpdate, admin: User = Depends(require_admin)):
    """Update user role or status (admin only)."""
    with session_scope() as s:
        user = s.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        
        changes = []
        if data.role is not None:
            user.role = data.role
            changes.append(f"role={data.role}")
        if data.full_name is not None:
            user.full_name = data.full_name
            changes.append(f"full_name={data.full_name}")
        if data.is_active is not None:
            user.is_active = data.is_active
            changes.append(f"is_active={data.is_active}")
        
        # Audit log
        s.add(AuditLog(
            id=uid(24),
            user_id=admin.id,
            action="user.update",
            target=user_id,
            detail_json=f'{{"changes": {str(changes)}}}',
        ))
        
        return UserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            full_name=user.full_name or "",
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else "",
        )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, admin: User = Depends(require_admin)):
    """Soft delete a user (admin only)."""
    with session_scope() as s:
        user = s.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        
        user.is_active = False
        
        # Audit log
        s.add(AuditLog(
            id=uid(24),
            user_id=admin.id,
            action="user.delete",
            target=user_id,
        ))


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = Query(100, le=1000),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    admin: User = Depends(require_admin),
):
    """Retrieve audit logs with filters (admin only)."""
    from sqlalchemy import select
    
    with session_scope() as s:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action.like(f"%{action}%"))
        
        rows = s.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "target": r.target,
                "detail": r.detail_json,
                "correlation_id": r.correlation_id,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]


@router.get("/stats")
async def get_system_stats(admin: User = Depends(require_admin)):
    """Get system statistics (admin only)."""
    with session_scope() as s:
        total_users = s.query(User).count()
        active_users = s.query(User).filter(User.is_active == True).count()
        total_conversations = s.query(Conversation).count()
        total_documents = s.query(Document).count()
        total_skills = s.query(Skill).count()
        
        av = availability()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_conversations": total_conversations,
            "total_documents": total_documents,
            "total_skills": total_skills,
            "local_llm_available": av.model_path_exists and av.llama_cpp_installed,
            "encryption_enabled": settings.encrypt_at_rest,
        }


class SystemStatusOut(BaseModel):
    version: str
    environment: str
    local_llm: dict
    encryption_at_rest: dict
    tools_mode: str
    updates_enabled: bool
    metrics_enabled: bool


@router.get("/status", response_model=SystemStatusOut)
async def system_status(admin: User = Depends(require_admin)) -> SystemStatusOut:
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
