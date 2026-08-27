"""Skills router — Skills Manager CRUD + built-in forking."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import delete_skill, get_skill, list_skills, record_audit, upsert_skill
from ..deps import require_lawyer
from ..models.db import User
from ..services.skills_manager import fork_builtin, select_relevant_skills, validate_skill_payload

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _serialize(s: dict[str, Any]) -> dict[str, Any]:
    return s


@router.get("")
async def get_skills(user: User = Depends(require_lawyer)) -> list[dict]:
    return [_serialize(s) for s in list_skills()]


@router.post("")
async def create_skill(payload: dict[str, Any],
                       user: User = Depends(require_lawyer)) -> dict:
    ok, err = validate_skill_payload(payload)
    if not ok:
        raise HTTPException(422, err)
    data = {**payload, "id": None, "owner_id": user.id,
            "builtin_key": None}
    saved = upsert_skill({k: v for k, v in data.items() if k != "id"})
    record_audit(user.id, "skill.created", target=saved["name"])
    return _serialize(get_full(saved))


def get_full(saved: dict) -> dict:
    return get_skill(saved["id"]) or saved


@router.patch("/{skill_id}")
async def patch_skill(skill_id: str, payload: dict[str, Any],
                      user: User = Depends(require_lawyer)) -> dict:
    existing = get_skill(skill_id)
    if existing is None:
        raise HTTPException(404, "skill not found")
    if existing.get("builtin_key") and existing.get("owner_id") is None:
        # built-ins are immutable → auto-fork an editable copy
        forked = fork_builtin(skill_id, user.id)
        assert forked is not None
        skill_id = forked["id"]
        existing = forked
    elif existing.get("owner_id") not in (None, user.id):
        raise HTTPException(403, "You can only edit your own skills.")
    ok, err = validate_skill_payload({**existing, **payload})
    if not ok:
        raise HTTPException(422, err)
    merged = {**{k: v for k, v in existing.items()
                 if k not in ("id", "triggers")}, **payload}
    upsert_skill({"id": skill_id, **merged})
    record_audit(user.id, "skill.updated", target=merged.get("name", skill_id))
    result = get_skill(skill_id)
    assert result is not None
    return _serialize(result)


@router.delete("/{skill_id}")
async def remove_skill(skill_id: str, user: User = Depends(require_lawyer)) -> dict:
    existing = get_skill(skill_id)
    if existing is None:
        raise HTTPException(404, "skill not found")
    if existing.get("builtin_key") and existing.get("owner_id") is None:
        raise HTTPException(400, "Built-in skills cannot be deleted; disable them instead.")
    if existing.get("owner_id") != user.id:
        raise HTTPException(403, "You can only delete your own skills.")
    delete_skill(skill_id, user.id)
    record_audit(user.id, "skill.deleted", target=existing.get("name", skill_id))
    return {"ok": True}


class MatchRequest(BaseModel):
    query: str
    mode: str = "api"


@router.post("/match")
async def match_skills(req: MatchRequest,
                       user: User = Depends(require_lawyer)) -> list[dict]:
    """Preview which skills the engine would inject for a query."""
    return select_relevant_skills(req.query, mode=req.mode)
