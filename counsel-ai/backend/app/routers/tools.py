"""Tools router — composio-style stub actions with consent gate."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models.schemas import ToolCallRequest, ToolPreview
from ..services.tools_stub import build_preview, execute_tool, list_tools

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolResult(BaseModel):
    successful: bool
    data: dict | None = None
    error: str | None = None


@router.get("", response_model=list[ToolPreview])
async def get_tools() -> list[ToolPreview]:
    return [ToolPreview(**t) for t in list_tools()]


@router.post("/{slug}/preview")
async def preview(slug: str, raw_input: dict) -> dict:
    """Renders what the tool WOULD do; shown inside the consent modal."""
    try:
        return build_preview(slug, raw_input)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{slug}/execute", response_model=ToolResult)
async def execute(slug: str, req: ToolCallRequest) -> ToolResult:
    """Only runs external-send tools when confirmed=true (consent modal)."""
    result = execute_tool(slug, req.input, req.confirmed)
    return ToolResult(**result)
