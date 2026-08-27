"""Authentication: bcrypt password hashing + JWT access/refresh tokens.

Roles: ``admin`` | ``lawyer`` | ``paralegal`` | ``readonly``.

* Access tokens: short-lived JWTs signed HS256 with the instance secret.
* Refresh tokens: opaque random values, stored hashed; revocable per user
  (logout / admin action). Rotation happens on every refresh.
* Bootstrap: on first run an ``admin`` account is created. Its one-time
  password is printed to the server log exactly once and the account is
  flagged ``must_change_password``.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Any, Literal, Optional

import jwt as pyjwt

from .config import settings
from .database import session_scope, uid
from .models.db import RefreshToken, User

log = logging.getLogger("counsel.auth")

Role = Literal["admin", "lawyer", "paralegal", "readonly"]
ROLES: tuple[str, ...] = ("admin", "lawyer", "paralegal", "readonly")


# ----------------------------------------------------------------- passwords


def hash_password(plain: str) -> str:
    import bcrypt

    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt

    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def password_issues(pw: str) -> list[str]:
    issues: list[str] = []
    if len(pw) < 10:
        issues.append("at least 10 characters")
    if not any(c.isdigit() for c in pw):
        issues.append("one number")
    if not any(c.isalpha() for c in pw):
        issues.append("one letter")
    return issues


# -------------------------------------------------------------------- tokens


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user: User, extra: dict[str, Any] | None = None) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "iat": now,
        "exp": now + settings.access_token_minutes * 60,
        "typ": "access",
        **(extra or {}),
    }
    return pyjwt.encode(payload, settings.jwt_secret_resolved, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        payload = pyjwt.decode(
            token,
            settings.jwt_secret_resolved,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "typ"]},
        )
        if payload.get("typ") != "access":
            return None
        return payload
    except pyjwt.PyJWTError:
        return None


def create_refresh_token(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    with session_scope() as s:
        s.add(
            RefreshToken(
                id=uid(16),
                user_id=user_id,
                token_hash=_token_hash(token),
                expires_at=time.time() + settings.refresh_token_days * 86400,
            )
        )
    return token


def rotate_refresh_token(raw_token: str) -> tuple[Optional[User], Optional[str]]:
    """Validate a refresh token; revoke it and issue a fresh pair."""
    h = _token_hash(raw_token)
    with session_scope() as s:
        row = (
            s.query(RefreshToken)
            .filter(RefreshToken.token_hash == h, RefreshToken.revoked.is_(False))
            .one_or_none()
        )
        if row is None or row.expires_at < time.time():
            return None, None
        user = s.get(User, row.user_id)
        if user is None or not user.is_active:
            return None, None
        row.revoked = True
    return user, create_refresh_token(user.id)


def revoke_all_sessions(user_id: str) -> int:
    with session_scope() as s:
        n = (
            s.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .update({"revoked": True})
        )
    return int(n)


# ------------------------------------------------------------------ users


def bootstrap_admin_if_needed() -> Optional[User]:
    """Create the first admin account when the users table is empty."""
    with session_scope() as s:
        if s.query(User).count() > 0:
            return None
        one_time_pw = secrets.token_urlsafe(12) + "!7"
        admin = User(
            id=uid(16),
            email="admin@counsel.local",
            name="Firm Administrator",
            password_hash=hash_password(one_time_pw),
            role="admin",
            must_change_password=True,
        )
        s.add(admin)
    log.warning(
        "BOOTSTRAP ADMIN CREATED — login admin@counsel.local / %s — change this "
        "password immediately after first login. This line will not appear again.",
        one_time_pw,
    )
    record_bootstrap_password_file(one_time_pw)
    return admin


def record_bootstrap_password_file(password: str) -> None:
    """Write the one-time admin password to data/bootstrap_admin.txt (0600).

    The file records a prominent notice to delete it after first login; the
    log line above is the primary channel.
    """
    try:
        p = settings.data_dir / "bootstrap_admin.txt"
        p.write_text(
            "ONE-TIME administrator password for admin@counsel.local:\n\n"
            f"    {password}\n\n"
            "Delete this file after signing in and changing the password.\n"
        )
        p.chmod(0o600)
    except OSError:  # pragma: no cover
        pass


def get_user(user_id: str) -> Optional[User]:
    with session_scope() as s:
        return s.get(User, user_id)


def get_user_by_email(email: str) -> Optional[User]:
    with session_scope() as s:
        return s.query(User).filter(User.email == email.lower().strip()).one_or_none()


def user_payload(user: User) -> dict[str, Any]:
    import json

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "must_change_password": bool(user.must_change_password),
        "practice_areas": json.loads(user.practice_areas_json or "[]"),
        "jurisdictions": json.loads(user.jurisdictions_json or "[]"),
        "accepted_disclaimer_at": user.accepted_disclaimer_at,
    }


def role_at_least(role: str, minimum: Role) -> bool:
    order: dict[str, int] = {"readonly": 0, "paralegal": 1, "lawyer": 2, "admin": 3}
    return order.get(role, -1) >= order[minimum]
