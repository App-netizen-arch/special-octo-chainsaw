"""Legal research agent.

Adapted from gpt-researcher (Apache-2.0): the plan -> search -> read -> write
loop, sub-query generation prompt style, context compression before writing,
and the deterministic ``## References`` appendix are preserved and rewritten
for this project.

Production additions:
* **Research cache** — identical queries within the TTL window return the
  stored report (hash of normalized query), cutting latency + provider load.
* **Audit trail** — every page fetch is an external transmission and is
  recorded (URL only, never content).
* **Verification hook** — after writing, lightweight symbolic checks run
  (citation existence + PII scan) and attach a verification summary.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Any, AsyncIterator, Callable, Optional

import httpx

from ..config import settings
from ..database import add_message, cache_get, cache_put, record_audit, session_scope
from ..models.db import ResearchCache
from ..utils.citation_normalizer import (
    normalize_all,
    parse_in_text_urls,
    references_appendix,
)
from ..utils.logging_setup import new_correlation_id
from ..utils.metrics import inc
from . import search_client
from .llm import complete
from .verification.pii_detector import detect_pii
from .verification.source_existence import verify_sources_exist

log = logging.getLogger("counsel.research")

# ------------------------------------------------------------------- prompts
# Prompt phrasing follows gpt-researcher's prompts.py (Apache-2.0), tightened
# for legal work and the citation contract used here.

SUBQUERY_PROMPT = (
    "Write up to {max_queries} short search queries to research this legal task: "
    "\"{task}\". Cover complementary angles such as governing law, limitation "
    "periods, leading authorities and recent amendments. Each query must be a "
    'plain natural language phrase — no site: operators. Respond ONLY as a JSON '
    'array of strings, e.g. ["limitation period breach of contract California", '
    '"..."].'
)

REPORT_SYSTEM = (
    "You are a meticulous legal research analyst. You write formal research "
    "memos for qualified lawyers using ONLY the supplied sources. You never "
    "invent statutes, cases or quotes. No emojis."
)

REPORT_PROMPT = (
    'Using the verified sources below, write a structured legal research memo '
    'answering: "{question}"\n\n'
    "Sources:\n\"\"\"\n{context}\n\"\"\"\n\n"
    "Requirements:\n"
    "1. Markdown with sections: Summary; Legal Position; Key Authorities; "
    "Risks & Caveats.\n"
    "2. Every substantive claim MUST carry an in-text markdown citation placed "
    "at the end of the sentence, like ([Source title](url)).\n"
    "3. Cite ONLY sources present above. If evidence is thin, say so plainly.\n"
    "4. Around {words} words. Formal register. No emojis."
)

SUMMARY_PROMPT = (
    "Compress the following research material into dense factual bullet points, "
    "preserving every URL and every statute/case name exactly as written:\n\n{context}"
)


# ------------------------------------------------------------- page fetching


async def _read_pages(urls: list[str], max_chars: int, user_id: str | None = None) -> list[dict]:
    """Fetch page text for whitelisted URLs (httpx + regex text extraction)."""
    cid = new_correlation_id()

    async def one(client: httpx.AsyncClient, url: str) -> dict:
        try:
            record_audit(user_id, "research.page_fetch", target=url, correlation_id=cid)
            resp = await client.get(url, follow_redirects=True)
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype:
                return {"url": url, "title": url, "raw_content": ""}
            html = resp.text
            title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else url
            body = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html)
            text = re.sub(r"(?s)<[^>]+>", " ", body)
            text = re.sub(r"&nbsp;?", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return {"url": url, "title": title[:200], "raw_content": text[:max_chars]}
        except httpx.HTTPError:
            return {"url": url, "title": url, "raw_content": ""}

    async with httpx.AsyncClient(
        timeout=15, headers={"User-Agent": "CounselAI/1.0 (+local legal workbench)"}
    ) as client:
        return list(await asyncio.gather(*(one(client, u) for u in urls)))


def _compress_context(pages: list[dict], max_total: int) -> str:
    """gpt-researcher-style compression: cap each doc, then cap the total."""
    parts: list[str] = []
    total = 0
    for p in pages:
        content = p.get("raw_content") or p.get("content") or ""
        if not content:
            continue
        take = content[: min(4000, max_total - total)]
        parts.append(f"[{p.get('title', '')}]({p['url']})\n{take}")
        total += len(take)
        if total >= max_total:
            break
    return "\n\n---\n\n".join(parts)


async def _generate_subqueries(query: str, llm_mode: str, api_key: Optional[str],
                               user_id: str | None = None) -> list[str]:
    try:
        raw = await complete(
            [{"role": "user", "content": SUBQUERY_PROMPT.format(
                max_queries=settings.research_max_subqueries, task=query)}],
            mode=llm_mode, api_key=api_key, max_tokens=200, user_id=user_id,
        )
        m = re.search(r"\[.*\]", raw, re.S)
        if m:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, list):
                return [str(q)[:160] for q in parsed if str(q).strip()][
                    : settings.research_max_subqueries]
    except Exception as exc:  # noqa: BLE001 - planning is best-effort
        log.info("subquery generation failed (%s); using heuristic", exc)
    kws = " ".join(search_client.keywords(query))
    return [f"{kws} statute limitations", f"{kws} case law"]


# --------------------------------------------------------------------- cache


def _cache_key(query: str) -> str:
    return hashlib.sha256(" ".join(query.lower().split()).encode()).hexdigest()


def _cache_lookup(query: str) -> Optional[dict[str, Any]]:
    try:
        row = cache_get(ResearchCache, ResearchCache.query_hash, _cache_key(query),
                        expires_col="expires_at")
        if row is not None:
            return json.loads(row.result_json)  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001
        log.debug("research cache miss (%s)", exc)
    return None


def _cache_store(query: str, result: dict[str, Any]) -> None:
    ttl = settings.cache_research_ttl_hours * 3600
    try:
        with session_scope() as s:
            s.merge(
                ResearchCache(
                    query_hash=_cache_key(query),
                    query_text=query[:500],
                    result_json=json.dumps(result),
                    created_at=time.time(),
                    expires_at=time.time() + ttl,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.debug("research cache store failed: %s", exc)


# --------------------------------------------------------------- main runner


async def run_research(
    query: str,
    llm_mode: str,
    api_key: Optional[str],
    emit: Optional[Callable[[dict], None]] = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    def progress(stage: str, detail: str = "") -> None:
        if emit:
            emit({"type": "research_progress", "stage": stage, "detail": detail})

    if use_cache:
        cached = _cache_lookup(query)
        if cached:
            progress("done", "served from local research cache")
            inc("research.cache_hits")
            return cached

    progress("planning", query)
    subqueries = await _generate_subqueries(query, llm_mode, api_key, user_id=user_id)

    progress("searching", "; ".join(subqueries))
    gathered: list[dict] = []
    provider_note = ""
    for sq in subqueries:
        try:
            results, provider = await search_client.web_search(
                sq, max_results=settings.research_max_results_per_query, user_id=user_id
            )
            provider_note = provider
            gathered.extend(results)
        except RuntimeError as exc:
            progress("error", str(exc))
            return {"report": "", "sources": [], "provider": "", "error": str(exc),
                    "verification": {}}

    # dedupe by URL across sub-queries, then read the top pages
    seen: set[str] = set()
    urls: list[str] = []
    for r in sorted(gathered, key=lambda x: -float(x.get("relevance") or 0)):
        u = r["url"]
        if u not in seen:
            seen.add(u)
            urls.append(u)
    urls = urls[:8]

    progress("reading", f"{len(urls)} legitimate sources")
    pages = await _read_pages(urls, settings.research_max_page_chars, user_id=user_id)

    # merge snippets for pages we could not fetch fully
    by_url = {p["url"]: p for p in pages}
    for r in gathered:
        p = by_url.setdefault(r["url"], {"url": r["url"], "title": r.get("title", ""), "raw_content": ""})
        if not p.get("raw_content"):
            p["raw_content"] = r.get("content", "")[:1500]

    progress("writing", "")
    context = _compress_context(pages, settings.research_max_context_chars)
    if len(context) > 12000:
        context = await complete(
            [{"role": "user", "content": SUMMARY_PROMPT.format(context=context)}],
            mode=llm_mode, api_key=api_key, max_tokens=1400, user_id=user_id,
        )

    report_body = await complete(
        [
            {"role": "system", "content": REPORT_SYSTEM},
            {"role": "user", "content": REPORT_PROMPT.format(question=query, context=context, words=600)},
        ],
        mode=llm_mode, api_key=api_key, max_tokens=1800, user_id=user_id,
    )

    cited_urls = parse_in_text_urls(report_body)
    cited_set = set(cited_urls)
    source_dicts = [
        {
            "title": p.get("title") or u,
            "url": u,
            "snippet": (p.get("raw_content") or "")[:300],
            "relevance": 1.0 if u in cited_set else 0.6,
            "kind": "web",
        }
        for p in pages
        for u in [p["url"]]
        if p.get("raw_content")
    ]
    sources = normalize_all(source_dicts)

    # ---- lightweight symbolic verification (chat/research level) -------------
    progress("verifying", "checking citations and privacy")
    source_payloads = [s.model_dump() for s in sources]
    existence = await verify_sources_exist(
        report_body, source_payloads, check_quotes=False,
        enabled=settings.verify_source_http, timeout=settings.source_check_timeout,
    )
    pii_report = detect_pii(report_body, include_names=True)
    verification = {
        "level": "light",
        "source_checks": existence,
        "pii": pii_report.summary(),
    }

    report = report_body.strip() + references_appendix(sources)
    result = {
        "report": report,
        "sources": source_payloads,
        "provider": provider_note,
        "error": "",
        "verification": verification,
    }
    if not result["report"].strip():
        return result
    _cache_store(query, result)
    inc("research.runs")
    progress("done", provider_note)
    return result


async def stream_research_events(
    query: str, llm_mode: str, api_key: Optional[str],
    user_id: str | None = None, conversation_id: str | None = None,
) -> AsyncIterator[dict]:
    """Async-generator variant used directly by the WebSocket handler."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def runner() -> None:
        try:
            result = await run_research(query, llm_mode, api_key, emit=emit,
                                        user_id=user_id, conversation_id=conversation_id)
            await queue.put({"type": "sources", "sources": result["sources"]})
            if result.get("verification"):
                await queue.put({"type": "verification", "report": result["verification"]})
            await queue.put({"type": "token", "content": result["report"]})
            await queue.put({"type": "done"})
        except Exception as exc:  # noqa: BLE001
            log.exception("research failed")
            await queue.put({"type": "error", "message": f"Research failed: {exc}"})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
    await task
