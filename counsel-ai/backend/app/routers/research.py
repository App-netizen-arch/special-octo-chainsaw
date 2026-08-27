"""Research router — REST mirror of the WebSocket research flow."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from ..deps import require_lawyer
from ..models.db import User
from ..services.research_agent import run_research

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str
    llm_mode: str = Field("api", description="LLM used for planning/writing: local|api")
    api_key: Optional[str] = None


class ResearchResponse(BaseModel):
    report: str
    sources: list[dict]
    provider: str
    error: str = ""
    verification: dict = {}


@router.post("", response_model=ResearchResponse)
async def research(req: ResearchRequest,
                   user: User = Depends(require_lawyer)) -> ResearchResponse:
    result = await asyncio.wait_for(
        run_research(req.query, req.llm_mode, req.api_key, user_id=user.id),
        timeout=240,
    )
    return ResearchResponse(**result)
