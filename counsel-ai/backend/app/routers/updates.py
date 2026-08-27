"""Legal updates router: list, manual refresh, impact summarization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import get_legal_update, list_legal_updates, record_audit
from ..deps import current_user, require_lawyer
from ..models.db import User
from ..services.scheduler import trigger_update_check_now

router = APIRouter(prefix="/api/updates", tags=["updates"])


class UpdateOut(BaseModel):
    id: str
    source: str
    title: str
    url: str
    published_at: float
    jurisdiction: str
    doc_type: str
    summary: str
    relevance: float
    impact_brief: str


@router.get("", response_model=list[UpdateOut])
async def get_updates(jurisdiction: str | None = None, limit: int = 100,
                      user: User = Depends(current_user)) -> list[UpdateOut]:
    return [UpdateOut(**u) for u in list_legal_updates(jurisdiction=jurisdiction,
                                                       limit=limit)]


@router.post("/check-now")
async def check_now(user: User = Depends(require_lawyer)) -> dict:
    """Manual 'Check for updates now' button."""
    result = await trigger_update_check_now()
    record_audit(user.id, "updates.manual_check", detail=result)
    return result


class ImpactRequest(BaseModel):
    llm_mode: str = "api"
    api_key: str | None = None


@router.post("/{update_id}/summarize-impact")
async def summarize_impact(update_id: str, req: ImpactRequest,
                           user: User = Depends(require_lawyer)) -> dict:
    from ..services.legal_updates import summarize_impact as _summarize

    if get_legal_update(update_id) is None:
        raise HTTPException(404, "update not found")
    brief = await _summarize(update_id, req.llm_mode, req.api_key, user_id=user.id)
    return {"id": update_id, "impact_brief": brief}
