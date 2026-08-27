"""Users & auth router: login, refresh, me, logout + admin user management."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from ..auth import (
    ROLES,
    create_access_token,
    create_refresh_token,
    get_user_by_email,
    hash_password,
    password_issues,
    revoke_all_sessions,
    rotate_refresh_token,
    uid,
    user_payload,
    verify_password,
)
from ..database import record_audit, session_scope
from ..deps import current_user, require_admin
from ..models.db import User

log = logging.getLogger("counsel.users")
router = APIRouter(prefix="/api/users", tags=["users"])


# --------------------------------------------------------------------- auth


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: dict


@router.post("/login", response_model=TokenPair)
async def login(req: LoginRequest) -> TokenPair:
    from ..config import settings

    user = get_user_by_email(req.email)
    if user is None or not verify_password(req.password, user.password_hash):
        record_audit(None, "auth.login_failed", target=req.email[:120])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    access = create_access_token(user)
    refresh = create_refresh_token(user.id)
    record_audit(user.id, "auth.login")
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in_minutes=settings.access_token_minutes,
        user=user_payload(user),
    )


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenPair)
async def refresh(req: RefreshRequest) -> TokenPair:
    from ..config import settings

    user, new_refresh = rotate_refresh_token(req.refresh_token)
    if user is None or new_refresh is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Session expired — sign in again.")
    return TokenPair(
        access_token=create_access_token(user),
        refresh_token=new_refresh,
        expires_in_minutes=settings.access_token_minutes,
        user=user_payload(user),
    )


@router.post("/logout")
async def logout(user: User = Depends(current_user)) -> dict:
    revoke_all_sessions(user.id)
    record_audit(user.id, "auth.logout")
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(current_user)) -> dict:
    return user_payload(user)


class AcceptDisclaimerRequest(BaseModel):
    accepted: bool


@router.post("/me/accept-disclaimer")
async def accept_disclaimer(_: AcceptDisclaimerRequest,
                            user: User = Depends(current_user)) -> dict:
    with session_scope() as s:
        u = s.get(User, user.id)
        if u:
            u.accepted_disclaimer_at = time.time()
    record_audit(user.id, "legal.disclaimer_accepted")
    return {"ok": True}


class MePatch(BaseModel):
    name: str | None = None
    practice_areas: list[str] | None = None
    jurisdictions: list[str] | None = None
    settings: dict[str, str] | None = None


@router.patch("/me")
async def patch_me(patch: MePatch, user: User = Depends(current_user)) -> dict:
    with session_scope() as s:
        u = s.get(User, user.id)
        if u is None:
            raise HTTPException(404, "user not found")
        if patch.name is not None:
            u.name = patch.name[:200]
        if patch.practice_areas is not None:
            u.practice_areas_json = json.dumps(patch.practice_areas[:30])
        if patch.jurisdictions is not None:
            u.jurisdictions_json = json.dumps(patch.jurisdictions[:20])
        if patch.settings is not None:
            current = json.loads(u.settings_json or "{}")
            safe_keys = {"country", "province", "city", "privacy_preference",
                         "domain_whitelist_json"}
            for k, v in patch.settings.items():
                if k in safe_keys:
                    current[k] = str(v)[:500]
            u.settings_json = json.dumps(current)
    return user_payload(get_user_by_email(user.email) or user)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/me/change-password")
async def change_password(req: ChangePasswordRequest,
                          user: User = Depends(current_user)) -> dict:
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    issues = password_issues(req.new_password)
    if issues and user.must_change_password is False:
        raise HTTPException(400, f"Password needs: {', '.join(issues)}.")
    with session_scope() as s:
        u = s.get(User, user.id)
        if u:
            u.password_hash = hash_password(req.new_password)
            u.must_change_password = False
    revoke_all_sessions(user.id)
    record_audit(user.id, "auth.password_changed")
    return {"ok": True, "message": "Password changed. Sign in again on your other devices."}


# ------------------------------------------------------------ admin surface


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = ""
    role: str = Field("lawyer")
    password: str = Field(..., min_length=10)


@router.get("", response_model=list[dict])
async def list_users(admin: User = Depends(require_admin)) -> list[dict]:
    with session_scope() as s:
        users = s.query(User).order_by(User.created_at).all()
        return [user_payload(u) | {"is_active": u.is_active} for u in users]


@router.post("", response_model=dict)
async def create_user(req: CreateUserRequest,
                      admin: User = Depends(require_admin)) -> dict:
    if req.role not in ROLES:
        raise HTTPException(400, f"Role must be one of {', '.join(ROLES)}.")
    if get_user_by_email(req.email):
        raise HTTPException(409, "A user with that email already exists.")
    issues = password_issues(req.password)
    if issues:
        raise HTTPException(400, f"Password needs: {', '.join(issues)}.")
    user = User(
        id=uid(16), email=req.email.lower(), name=req.name[:200],
        password_hash=hash_password(req.password), role=req.role,
        must_change_password=True,
    )
    with session_scope() as s:
        s.add(user)
    record_audit(admin.id, "admin.user_created", target=req.email,
                 detail={"role": req.role})
    return user_payload(user)


class PatchUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.patch("/{user_id}", response_model=dict)
async def patch_user(user_id: str, patch: PatchUserRequest,
                     admin: User = Depends(require_admin)) -> dict:
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")
        if patch.role is not None:
            if patch.role not in ROLES:
                raise HTTPException(400, f"Role must be one of {', '.join(ROLES)}.")
            if u.id == admin.id and patch.role != "admin":
                raise HTTPException(400, "You cannot demote your own account.")
            u.role = patch.role
            record_audit(admin.id, "admin.user_role_changed", target=u.email,
                         detail={"role": patch.role})
        if patch.is_active is not None:
            if u.id == admin.id and patch.is_active is False:
                raise HTTPException(400, "You cannot disable your own account.")
            u.is_active = patch.is_active
            record_audit(admin.id, "admin.user_active_changed", target=u.email,
                         detail={"is_active": patch.is_active})
            if not patch.is_active:
                revoke_all_sessions(u.id)
        payload = user_payload(u) | {"is_active": u.is_active}
    return payload
