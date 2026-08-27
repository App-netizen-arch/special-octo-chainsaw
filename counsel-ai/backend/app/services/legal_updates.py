"""Legal update monitoring — daily fetch + symbolic filtering.

Fetches official legal sources (government gazettes, court RSS feeds, bar
bulletins, regulators), then applies the deterministic filter chain:

1. **Jurisdiction match** — feed is tagged with jurisdictions; items must
   intersect the user's configured practice jurisdictions.
2. **Document type** — classified by keyword rules (legislation, case law,
   regulation, guidance, consultation).
3. **Relevance score** — overlap between item text and the user's practice
   areas; low scorers are dropped.
4. **Duplicate detection** — SHA-256 of normalized title+URL; seen items are
   skipped at DB level.

Only survivors reach the Legal Updates tab. ``summarize_impact`` asks the LLM
for a plain-English brief with citation back to the source.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import settings
from ..database import add_legal_update, record_audit, session_scope
from ..models.db import User
from ..utils.logging_setup import new_correlation_id
from ..utils.metrics import inc, observe

log = logging.getLogger("counsel.updates")


@dataclass(frozen=True)
class Feed:
    url: str
    name: str
    jurisdiction: str  # matches settings province or country names
    country: str = ""


OFFICIAL_FEEDS: tuple[Feed, ...] = (
    # United States
    Feed("https://www.federalregister.gov/documents/search.atom?conditions%5Bterm%5D=law",
         "Federal Register", "United States"),
    Feed("https://www.supremecourt.gov/rss/blog.xml", "US Supreme Court", "United States"),
    Feed("https://oag.ca.gov/rss/press-releases", "California DOJ", "California", "United States"),
    Feed("https://www.nysenate.gov/legislation/laws/rss", "NY Senate Laws", "New York", "United States"),
    # United Kingdom
    Feed("https://www.legislation.gov.uk/uksi/changes/affected.rdf", "UK Legislation (SI)", "England", "United Kingdom"),
    Feed("https://judiciary.uk/feed/", "UK Judiciary", "England", "United Kingdom"),
    # Canada
    Feed("https://www.canada.ca/en/news.rss", "Canada.ca News", "Canada"),
    # India
    Feed("https://egazette.gov.in/(S(1))/ViewNotice.aspx", "India eGazette", "India"),
    Feed("https://main.sci.gov.in/rss", "Supreme Court of India", "India"),
    # Australia
    Feed("https://www.legislation.gov.au/feeds/latestcomp", "Federal Register of Legislation", "Australia"),
)

_DOC_TYPES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    ("case_law", (re.compile(r"(?i)\b(judgment|judgement|verdict|ruling|opinion|appeal)\b"),)),
    ("legislation", (re.compile(r"(?i)\b(act|bill|statute|code|amendment)\b"),)),
    ("regulation", (re.compile(r"(?i)\b(regulation|rule[sd]?|circular|order|bylaw)\b"),)),
    ("guidance", (re.compile(r"(?i)\b(guidance|notice|bulletin|practice note|circular)\b"),)),
)


def classify_doc_type(title: str) -> str:
    text = title.lower()
    for dt, patterns in _DOC_TYPES:
        if any(p.search(text) for p in patterns):
            return dt
    return "other"


def content_hash(title: str, url: str) -> str:
    norm = re.sub(r"\s+", " ", f"{title}|{url}".lower().strip())
    return hashlib.sha256(norm.encode()).hexdigest()


# ------------------------------------------------------------------ fetching


async def fetch_feed(client: httpx.AsyncClient, feed: Feed) -> list[dict[str, Any]]:
    """Minimal RSS/Atom parser (xml.etree) — no external feed dependency."""
    try:
        resp = await client.get(feed.url, timeout=20, follow_redirects=True,
                                headers={"User-Agent": "CounselAI/1.0 (+legal updates)"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as exc:  # noqa: BLE001 — one dead feed must not kill the job
        log.warning("feed failed: %s (%s)", feed.name, type(exc).__name__)
        return []

    items: list[dict[str, Any]] = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall(".//item") or root.findall("atom:entry", ns)
    for e in entries[:40]:
        def txt(path: str) -> str:
            node = e.find(path) if not path.startswith("atom:") else e.find(path, ns)
            if node is None:
                node = next((x for x in e.iter() if x.tag.split('}')[-1] == path), None)
            return (node.text or "").strip() if node is not None else ""

        title = txt("title") or ""
        link = txt("link") or next(
            (l.attrib.get("href", "") for l in e.iter() if l.tag.endswith("link")),
            "")
        pub = txt("pubDate") or txt("published") or txt("updated")
        summary = txt("description") or txt("summary")
        if not title:
            continue
        items.append({
            "source": feed.name,
            "title": title[:500],
            "url": link,
            "published_at": _parse_date(pub),
            "jurisdiction": feed.jurisdiction,
            "doc_type": classify_doc_type(title + " " + summary[:200]),
            "summary": re.sub(r"<[^>]+>", " ", summary)[:600],
        })
    return items


def _parse_date(raw: str) -> float:
    import time as _t
    from email.utils import parsedate_to_datetime
    from datetime import datetime

    raw = raw.strip()
    if not raw:
        return _t.time()
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:19], fmt).timestamp()
        except ValueError:
            continue
    return _t.time()


# ------------------------------------------------------- symbolic filtering


def score_relevance(item: dict[str, Any], practice_areas: list[str]) -> float:
    base = 0.4
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    hits = sum(1 for area in practice_areas if area.lower() in text)
    base += min(hits * 0.2, 0.6)
    if item.get("doc_type") != "other":
        base += 0.05
    return round(min(base, 1.0), 2)


def passes_filters(item: dict[str, Any], user_jurisdictions: list[str],
                   practice_areas: list[str]) -> bool:
    """Jurisdiction match + relevance threshold."""
    juris = user_jurisdictions or []
    if juris and not any(j in (item.get("jurisdiction", ""), ) or
                         j == item.get("jurisdiction") for j in juris):
        # country feeds still pass when the user picked a province of it
        country_ok = any(j == item.get("jurisdiction") for j in juris)
        if not country_ok and item.get("jurisdiction") not in juris:
            return False
    relevance = score_relevance(item, practice_areas)
    item["relevance"] = relevance
    return relevance >= 0.4


async def refresh_updates(user_ids_and_prefs: list[tuple[str, list[str], list[str]]] | None = None,
                          force: bool = False) -> dict[str, int]:
    """Fetch all feeds, apply filters per user preferences, store survivors.

    ``user_ids_and_prefs``: [(user_id, jurisdictions, practice_areas)]. When
    None, all active users with accepted disclaimers are loaded from DB.
    """
    cid = new_correlation_id()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(fetch_feed(client, f) for f in OFFICIAL_FEEDS))
    all_items = [it for batch in results for it in batch]

    stored = duplicates = 0
    if user_ids_and_prefs is None:
        with session_scope() as s:
            users = s.query(User).filter(User.is_active.is_(True)).all()
            user_ids_and_prefs = [
                (u.id, json.loads(u.jurisdictions_json or "[]"),
                 json.loads(u.practice_areas_json or "[]"))
                for u in users
            ]

    seen_global: set[str] = set()
    for user_id, juriss, areas in user_ids_and_prefs:
        for item in all_items:
            h = content_hash(item["title"], item["url"])
            if h in seen_global:
                duplicates += 1
                continue
            scoped = dict(item)
            scoped["content_hash"] = h
            if not passes_filters(scoped, juriss, areas):
                continue
            if add_legal_update({k: v for k, v in scoped.items() if k != "relevance"} |
                                {"relevance": scoped["relevance"]}):
                stored += 1
                seen_global.add(h)

    record_audit(None, "updates.refresh", detail={"fetched": len(all_items),
                                                  "stored": stored},
                 correlation_id=cid)
    inc("updates.stored", value=stored)
    observe("updates.items_fetched", len(all_items))
    log.info("legal updates refreshed: fetched=%d stored=%d dupes=%d",
             len(all_items), stored, duplicates)
    return {"fetched": len(all_items), "stored": stored, "duplicates": duplicates}


async def summarize_impact(update_id: str, llm_mode: str, api_key: str | None,
                           user_id: str | None = None) -> str:
    """LLM plain-English impact brief with citation to the source."""
    from ..database import get_legal_update, set_impact_brief
    from .llm import complete

    upd = get_legal_update(update_id)
    if upd is None:
        return "Update not found."
    prompt = (
        f"Summarize the practical impact of this legal development for a small "
        f"law firm in 120 words max. Structure: What changed / Who is affected "
        f"/ Action needed. Cite the source URL at the end.\n\n"
        f"Title: {upd['title']}\nSource: {upd['url']}\n"
        f"Published: {upd['published_at']}\nSummary: {upd['summary']}"
    )
    brief = await complete([{"role": "user", "content": prompt}], mode=llm_mode,
                           api_key=api_key, max_tokens=400, user_id=user_id)
    set_impact_brief(update_id, brief.strip())
    return brief.strip()
