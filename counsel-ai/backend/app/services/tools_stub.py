"""Tools service — composio-style action stubs.

Adapted from composio's tool interface (Apache-2.0): each tool is a frozen
definition of {slug, name, description, input_schema (JSON Schema), execute}.
Execution returns the composio envelope {data, error, successful}. For the
MVP every action is SIMULATED: it renders a preview and writes a dummy output
file locally; no external API is ever called.

The consent gate lives in the router: execute requires confirmed=true, which
the Flutter app only sends after its "This action will send data externally"
modal.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from ..config import settings


# ------------------------------------------------------------- input schemas


class DraftEmailInput(BaseModel):
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., min_length=1, description="Email body text")
    cc: list[str] = Field(default_factory=list)


class CreateEventInput(BaseModel):
    title: str = Field(..., description="Event title")
    date: str = Field(..., description="Date in YYYY-MM-DD")
    time: str = Field("09:00", description="Start time HH:MM")
    duration_minutes: int = Field(60, ge=5, le=720)
    location: str = ""
    attendees: list[str] = Field(default_factory=list)


class SaveNoteInput(BaseModel):
    title: str
    content_markdown: str


# ------------------------------------------------------------------ registry

ToolHandler = Callable[[BaseModel], dict]


def _write_output(name: str, payload: str) -> Path:
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = settings.outputs_dir / f"{stamp}-{name}"
    path.write_text(payload, encoding="utf-8")
    return path


def _exec_draft_email(inp: DraftEmailInput) -> dict:
    lines = [
        "SIMULATED EMAIL (no external service was contacted)",
        "=" * 55,
        f"To:      {inp.to}",
        f"Cc:      {', '.join(inp.cc) if inp.cc else '-'}",
        f"Subject: {inp.subject}",
        "",
        inp.body,
    ]
    path = _write_output("email.txt", "\n".join(lines))
    return {"simulated": True, "output_file": str(path), "preview": "\n".join(lines)}


def _exec_create_event(inp: CreateEventInput) -> dict:
    end_hour, end_min = divmod(
        int(inp.time.split(":")[0]) * 60 + int(inp.time.split(":")[1]) + inp.duration_minutes, 60
    )
    event = {
        "title": inp.title,
        "date": inp.date,
        "start": inp.time,
        "end": f"{end_hour % 24:02d}:{end_min:02d}",
        "location": inp.location or None,
        "attendees": inp.attendees,
    }
    ics = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CounselAI//MVP//EN",
        "BEGIN:VEVENT",
        f"SUMMARY:{inp.title}",
        f"DTSTART;VALUE=DATE-TIME:{inp.date.replace('-', '')}T{inp.time.replace(':', '')}00",
        f"DTEND;VALUE=DATE-TIME:{inp.date.replace('-', '')}T{end_hour % 24:02d}{end_min:02d}00",
        f"LOCATION:{inp.location}" if inp.location else "",
        f"DESCRIPTION:Simulated by Counsel AI tools stub",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    path = _write_output("event.ics", "\n".join(x for x in ics if x))
    return {"simulated": True, "event": event, "output_file": str(path)}


def _exec_save_note(inp: SaveNoteInput) -> dict:
    safe = "".join(c for c in inp.title if c.isalnum() or c in " -_").strip() or "note"
    path = _write_output(f"{safe}.mdx", inp.content_markdown)
    return {"simulated": False, "saved_to": str(path)}


class ToolDef:
    def __init__(
        self,
        slug: str,
        name: str,
        description: str,
        input_model: type[BaseModel],
        handler: ToolHandler,
        requires_external_send: bool = True,
    ) -> None:
        self.slug = slug
        self.name = name
        self.description = description
        self.input_model = input_model
        self.handler = handler
        self.requires_external_send = requires_external_send

    @property
    def input_schema(self) -> dict:
        return self.input_model.model_json_schema()


TOOLS: dict[str, ToolDef] = {
    t.slug: t
    for t in (
        ToolDef(
            "DRAFT_EMAIL",
            "Draft Email",
            "Compose an email from the current document or chat context. Simulated: writes a preview file, sends nothing.",
            DraftEmailInput,
            lambda i: _exec_draft_email(DraftEmailInput(**i)),
        ),
        ToolDef(
            "CREATE_CALENDAR_EVENT",
            "Create Calendar Event",
            "Create a calendar event such as a filing deadline. Simulated: writes a local .ics file.",
            CreateEventInput,
            lambda i: _exec_create_event(CreateEventInput(**i)),
        ),
        ToolDef(
            "SAVE_NOTE",
            "Save Note Locally",
            "Save markdown content as a note file on this machine only.",
            SaveNoteInput,
            lambda i: _exec_save_note(SaveNoteInput(**i)),
            requires_external_send=False,
        ),
    )
}


def list_tools() -> list[dict]:
    return [
        {
            "slug": t.slug,
            "name": t.name,
            "description": t.description,
            "requires_external_send": t.requires_external_send,
            "input_schema": t.input_schema,
        }
        for t in TOOLS.values()
    ]


def build_preview(slug: str, raw_input: dict[str, Any]) -> dict:
    """Human-readable preview shown inside the consent modal."""
    if slug not in TOOLS:
        raise KeyError(f"Unknown tool: {slug}")
    tool = TOOLS[slug]
    try:
        parsed = tool.input_model(**raw_input)
    except Exception as exc:  # noqa: BLE001 - surface validation nicely
        raise ValueError(f"Invalid input for {tool.name}: {exc}") from exc
    fields = {k: v for k, v in parsed.model_dump().items()}
    return {"slug": slug, "name": tool.name, "fields": fields, "requires_external_send": tool.requires_external_send}


def execute_tool(slug: str, raw_input: dict[str, Any], confirmed: bool) -> dict:
    """Composio-style envelope: {successful, data, error}."""
    if slug not in TOOLS:
        return {"successful": False, "error": f"Unknown tool '{slug}'", "data": None}
    tool = TOOLS[slug]
    if tool.requires_external_send and not confirmed:
        return {
            "successful": False,
            "error": "Consent required. The user must confirm this action in the app before it runs.",
            "data": None,
        }
    try:
        data = tool.handler(raw_input)
        return {"successful": True, "data": data, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"successful": False, "error": str(exc), "data": None}
