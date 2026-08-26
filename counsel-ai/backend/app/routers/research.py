"""Research router — REST mirror of the WebSocket research flow."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

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


@router.post("", response_model=ResearchResponse)
async def research(req: ResearchRequest) -> ResearchResponse:
    result = await asyncio.wait_for(
        run_research(req.query, req.llm_mode, req.api_key),
        timeout=240,
    )
    return ResearchResponse(**result)
