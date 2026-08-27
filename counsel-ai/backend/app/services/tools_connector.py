"""Tool actions — real connectors (Gmail, Outlook, Calendar) + simulate mode.

Adapted from composio's action interface (Apache-2.0): every tool is a frozen
definition {slug, name, description, input schema, handler} returning the
composio-style envelope {successful, data, error}.

Production behaviour:

* **simulate** (default) — renders exactly what WOULD happen and writes a
  local artifact (.eml/.ics); nothing leaves the machine.
* **live** — performs the real call over OAuth2 REST APIs:
    * Gmail  : gmail.googleapis.com  (send / create-draft)
    * Microsoft Graph: graph.microsoft.com (sendMail / events)
  Tokens are exchanged via the installed-app OAuth flow, stored in the OS
  keychain through ``keyring``, and refreshed automatically.

The consent gate lives in the router: execute requires ``confirmed=true``
which the Flutter app only sends after its consent modal. Every execution —
simulated or live — is written to the audit trail.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

from ..config import settings
from ..database import record_audit
from ..utils.logging_setup import new_correlation_id

log = logging.getLogger("counsel.tools")

KEYRING_SERVICE = "CounselAI"


# ------------------------------------------------------------- input schemas


class DraftEmailInput(BaseModel):
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., min_length=1, description="Email body text")
    cc: list[str] = Field(default_factory=list)
    send_now: bool = Field(False, description="Send immediately (false = save as draft)")


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


@dataclass
class ToolDef:
    slug: str
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], dict]
    requires_external_send: bool = True
    provider: str | None = None  # google|microsoft|None(local)

    @property
    def input_schema(self) -> dict:
        return self.input_model.model_json_schema()


def _write_output(name: str, payload: str) -> Path:
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = settings.outputs_dir / f"{stamp}-{name}"
    path.write_text(payload, encoding="utf-8")
    return path


# ------------------------------------------------------------------- OAuth


GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_SEND = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_DRAFT = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
GCAL_EVENTS = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

MS_AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MS_SENDMAIL = "https://graph.microsoft.com/v1.0/me/sendMail"
MS_EVENTS = "https://graph.microsoft.com/v1.0/me/events"

SCOPES_GOOGLE = ["https://mail.google.com/", "https://www.googleapis.com/auth/calendar.events"]
SCOPES_MICROSOFT = ["Mail.Send", "Calendars.ReadWrite", "offline_access"]


def oauth_start_url(provider: str) -> tuple[str, str]:
    """Returns (authorization_url, state). State is verified on callback."""
    state = secrets.token_urlsafe(24)
    redirect = settings.tools_redirect_uri
    if provider == "google":
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": " ".join(SCOPES_GOOGLE),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH}?{urlencode(params)}", state
    params = {
        "client_id": settings.microsoft_client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(SCOPES_MICROSOFT),
        "state": state,
    }
    return f"{MS_AUTH}?{urlencode(params)}", state


async def oauth_exchange_code(provider: str, code: str) -> dict[str, Any]:
    """Exchange an auth code for tokens; persists them in the OS keychain."""
    if provider == "google":
        token_url, client_id, client_secret = GOOGLE_TOKEN, settings.google_client_id, settings.google_client_secret
        scope = " ".join(SCOPES_GOOGLE)
    else:
        token_url, client_id, client_secret = MS_TOKEN, settings.microsoft_client_id, settings.microsoft_client_secret
        scope = " ".join(SCOPES_MICROSOFT)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(token_url, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": settings.tools_redirect_uri,
            "grant_type": "authorization_code",
            **({"scope": scope} if provider == "google" else {}),
        })
        resp.raise_for_status()
        tokens = resp.json()
    _store_tokens(provider, tokens)
    return {"provider": provider, "stored": True}


def _store_tokens(provider: str, tokens: dict[str, Any]) -> None:
    payload = {**tokens, "_saved_at": time.time()}
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, f"{provider}-oauth", json.dumps(payload))
    except Exception:  # noqa: BLE001 — fall back to file with tight perms
        p = settings.data_dir / f".{provider}_oauth.json"
        p.write_text(json.dumps(payload))
        p.chmod(0o600)


def _load_tokens(provider: str) -> dict[str, Any] | None:
    try:
        import keyring

        raw = keyring.get_password(KEYRING_SERVICE, f"{provider}-oauth")
        if raw:
            return json.loads(raw)
    except Exception:  # noqa: BLE001
        pass
    p = settings.data_dir / f".{provider}_oauth.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None
    return None


async def _access_token(provider: str) -> str | None:
    """Return a valid access token, refreshing when needed."""
    tokens = _load_tokens(provider)
    if not tokens:
        return None
    expires_at = float(tokens.get("_saved_at", 0)) + int(tokens.get("expires_in", 3600))
    if time.time() < expires_at - 60:
        return str(tokens.get("access_token"))
    refresh = tokens.get("refresh_token")
    if not refresh:
        return None
    token_url = GOOGLE_TOKEN if provider == "google" else MS_TOKEN
    client_id = settings.google_client_id if provider == "google" else settings.microsoft_client_id
    client_secret = (
        settings.google_client_secret if provider == "google" else settings.microsoft_client_secret
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(token_url, data={
            "refresh_token": refresh,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        })
        if resp.status_code != 200:
            return None
        fresh = resp.json()
    merged = {**tokens, **fresh}
    _store_tokens(provider, merged)
    return str(merged.get("access_token"))


# ------------------------------------------------------------------ handlers


def _exec_draft_email(inp: DraftEmailInput) -> dict:
    """Simulated email: local .eml preview, nothing sent."""
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


def _mime_email(inp: DraftEmailInput) -> str:
    headers = [f"To: {inp.to}", f"Subject: {inp.subject}"]
    if inp.cc:
        headers.append(f"Cc: {', '.join(inp.cc)}")
    boundary = "=_counsel_boundary"
    body = (
        "\r\n".join(headers)
        + f"\r\nMIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary=\"{boundary}\"\r\n\r\n"
        + f"--{boundary}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{inp.body}\r\n"
        + f"--{boundary}--"
    )
    return body


async def _exec_send_gmail(inp: DraftEmailInput) -> dict:
    token = await _access_token("google")
    if not token:
        raise RuntimeError("Google account is not connected. Connect it in Settings > Tools first.")
    url = GMAIL_SEND if inp.send_now else GMAIL_DRAFT
    raw = base64.urlsafe_b64encode(_mime_email(inp).encode()).decode()
    payload = {"raw": raw} if inp.send_now else {"message": {"raw": raw}}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload,
                                 headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        data = resp.json()
    return {"sent_live": True, "provider": "gmail",
            "id": data.get("id"), "thread_id": data.get("threadId")}


async def _exec_send_outlook(inp: DraftEmailInput) -> dict:
    token = await _access_token("microsoft")
    if not token:
        raise RuntimeError("Microsoft account is not connected. Connect it in Settings > Tools first.")
    msg = {
        "message": {
            "subject": inp.subject,
            "body": {"contentType": "Text", "content": inp.body},
            "toRecipients": [{"emailAddress": {"address": inp.to}}],
        }
    }
    if inp.send_now:
        url = MS_SENDMAIL
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=msg,
                                     headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
        return {"sent_live": True, "provider": "outlook"}
    msg["message"]["isDraft"] = True
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://graph.microsoft.com/v1.0/me/messages",
                                 json={"message": msg["message"]},
                                 headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return {"sent_live": False, "drafted_live": True,
                "id": resp.json().get("id"), "provider": "outlook"}


def _exec_create_event(inp: CreateEventInput) -> dict:
    end_min_total = int(inp.time.split(":")[0]) * 60 + int(inp.time.split(":")[1]) + inp.duration_minutes
    event = {
        "title": inp.title,
        "date": inp.date,
        "start": inp.time,
        "end": f"{end_min_total // 60 % 24:02d}:{end_min_total % 60:02d}",
        "location": inp.location or None,
        "attendees": inp.attendees,
    }
    ics = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CounselAI//EN", "BEGIN:VEVENT",
        f"SUMMARY:{inp.title}",
        f"DTSTART;VALUE=DATE-TIME:{inp.date.replace('-', '')}T{inp.time.replace(':', '')}00",
        f"DTEND;VALUE=DATE-TIME:{inp.date.replace('-', '')}T{end_min_total // 60 % 24:02d}{end_min_total % 60:02d}00",
        f"LOCATION:{inp.location}" if inp.location else "",
        "DESCRIPTION:Created by Counsel AI",
        "END:VEVENT", "END:VCALENDAR",
    ]
    path = _write_output("event.ics", "\n".join(x for x in ics if x))
    return {"simulated": True, "event": event, "output_file": str(path)}


async def _exec_event_google(inp: CreateEventInput) -> dict:
    token = await _access_token("google")
    if not token:
        raise RuntimeError("Google account is not connected.")
    start_dt = f"{inp.date}T{inp.time}:00"
    end_h, end_m = divmod(int(inp.time.split(':')[0]) * 60 + int(inp.time.split(':')[1]) + inp.duration_minutes, 60)
    end_dt = f"{inp.date}T{end_h:02d}:{end_m:02d}:00"
    payload: dict[str, Any] = {"summary": inp.title, "start": {"dateTime": start_dt},
                               "end": {"dateTime": end_dt}}
    if inp.location:
        payload["location"] = inp.location
    if inp.attendees:
        payload["attendees"] = [{"email": a} for a in inp.attendees]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GCAL_EVENTS, json=payload,
                                 headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return {"created_live": True, "provider": "google_calendar",
                "id": resp.json().get("htmlLink")}


async def _exec_event_outlook(inp: CreateEventInput) -> dict:
    token = await _access_token("microsoft")
    if not token:
        raise RuntimeError("Microsoft account is not connected.")
    end_total = int(inp.time.split(':')[0]) * 60 + int(inp.time.split(':')[1]) + inp.duration_minutes
    payload = {
        "subject": inp.title,
        "start": {"dateTime": f"{inp.date}T{inp.time}:00", "timeZone": "UTC"},
        "end": {"dateTime": f"{inp.date}T{end_total // 60:02d}:{end_total % 60:02d}:00",
                "timeZone": "UTC"},
    }
    if inp.attendees:
        payload["attendees"] = [{"emailAddress": {"address": a}} for a in inp.attendees]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(MS_EVENTS, json=payload,
                                 headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return {"created_live": True, "provider": "outlook_calendar",
                "id": resp.json().get("id")}


def _exec_save_note(inp: SaveNoteInput) -> dict:
    safe = "".join(c for c in inp.title if c.isalnum() or c in " -_").strip() or "note"
    path = _write_output(f"{safe}.mdx", inp.content_markdown)
    return {"simulated": False, "saved_to": str(path)}


# ------------------------------------------------------------------ registry


TOOLS: dict[str, ToolDef] = {}


def _register_all() -> None:
    email_handler: Callable[[BaseModel], dict]

    def _email_dispatch(i: dict) -> dict:
        parsed = DraftEmailInput(**i)
        if settings.tools_mode == "live":
            # prefer whichever provider is connected
            if _load_tokens("google"):
                import asyncio

                return asyncio.get_event_loop().run_until_complete(_exec_send_gmail(parsed))
            if _load_tokens("microsoft"):
                import asyncio

                return asyncio.get_event_loop().run_until_complete(_exec_send_outlook(parsed))
        return _exec_draft_email(parsed)

    def _event_dispatch(i: dict) -> dict:
        parsed = CreateEventInput(**i)
        if settings.tools_mode == "live":
            if _load_tokens("google"):
                import asyncio

                return asyncio.get_event_loop().run_until_complete(_exec_event_google(parsed))
            if _load_tokens("microsoft"):
                import asyncio

                return asyncio.get_event_loop().run_until_complete(_exec_event_outlook(parsed))
        return _exec_create_event(parsed)

    TOOLS.update(
        {
            t.slug: t
            for t in (
                ToolDef(
                    "DRAFT_EMAIL", "Draft Email",
                    "Compose an email from context. Simulate mode saves a local "
                    "preview; connect an account to send for real.",
                    DraftEmailInput, _email_dispatch,
                ),
                ToolDef(
                    "CREATE_CALENDAR_EVENT", "Create Calendar Event",
                    "Create an event such as a filing deadline. Simulate mode "
                    "writes a local .ics; connect an account for live creation.",
                    CreateEventInput, _event_dispatch,
                ),
                ToolDef(
                    "SAVE_NOTE", "Save Note Locally",
                    "Save markdown content as a note file on this machine only.",
                    SaveNoteInput,
                    lambda i: _exec_save_note(SaveNoteInput(**i)),
                    requires_external_send=False,
                ),
            )
        }
    )


_register_all()


# ------------------------------------------------------------------ public API


def list_tools() -> list[dict]:
    return [
        {
            "slug": t.slug,
            "name": t.name,
            "description": t.description,
            "requires_external_send": t.requires_external_send,
            "input_schema": t.input_schema,
            "mode": "live" if settings.tools_mode == "live" else "simulate",
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
    except Exception as exc:  # noqa: BLE001 — surface validation nicely
        raise ValueError(f"Invalid input for {tool.name}: {exc}") from exc
    fields = parsed.model_dump()
    redacted = {k: (v[:80] + "…" if isinstance(v, str) and len(v) > 83 else v)
                for k, v in fields.items()}
    mode = "live" if settings.tools_mode == "live" else "simulate"
    return {"slug": slug, "name": tool.name, "fields": redacted,
            "requires_external_send": tool.requires_external_send,
            "mode": mode}


def execute_tool(slug: str, raw_input: dict[str, Any], confirmed: bool,
                 user_id: str | None = None) -> dict:
    """Composio-style envelope: {successful, data, error}. Audited."""
    if slug not in TOOLS:
        return {"successful": False, "error": f"Unknown tool '{slug}'", "data": None}
    tool = TOOLS[slug]
    if tool.requires_external_send and not confirmed:
        record_audit(user_id, "tool.consent_missing", target=slug)
        return {
            "successful": False,
            "error": "Consent required. The user must confirm this action in the app before it runs.",
            "data": None,
        }
    cid = new_correlation_id()
    try:
        data = tool.handler(raw_input)
        simulated = bool(data.get("simulated")) or slug == "SAVE_NOTE"
        record_audit(
            user_id, "tool.execute", target=slug,
            detail={"mode": "simulate" if simulated else "live",
                    "external_transmission": not simulated},
            correlation_id=cid,
        )
        return {"successful": True, "data": data, "error": None}
    except Exception as exc:  # noqa: BLE001
        log.exception("tool %s failed", slug)
        record_audit(user_id, "tool.error", target=slug, detail={"error": str(exc)[:300]},
                     correlation_id=cid)
        return {"successful": False, "error": _friendly_tool_error(exc), "data": None}


def _friendly_tool_error(exc: Exception) -> str:
    text = str(exc)
    if "not connected" in text:
        return text
    if "401" in text or "Unauthorized" in text:
        return "The connected account rejected the request — reconnect it in Settings > Tools."
    return f"The action could not be completed: {text[:300]}"
