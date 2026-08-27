"""Source existence verification.

For every URL cited in a generated document, performs an HTTP GET and:

1. Requires status 200 (429/5xx => "unverifiable", not "missing").
2. When quote-checking is enabled, extracts page text and fuzzy-matches the
   snippet against it (normalized token overlap + difflib ratio).

Results are deterministic dicts consumed by the orchestrator and UI. Network
failures degrade to ``unverified`` with a reason — they never fabricate a
pass. A local in-memory TTL cache prevents hammering the same host repeatedly
within one session.
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

log = logging.getLogger("counsel.verify.sources")

_URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 900  # 15 min


@dataclass
class SourceCheck:
    url: str
    status: str            # verified|exists|unverified|dead
    http_status: int | None = None
    quote_match: float | None = None
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "status": self.status,
            "http_status": self.http_status,
            "quote_match": round(self.quote_match, 3) if self.quote_match is not None else None,
            "detail": self.detail,
        }


def _normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text.lower())
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return text.strip()


def _quote_ratio(quote: str, page_text: str) -> float:
    """Fuzzy containment score of `quote` inside `page_text` (0..1)."""
    q = _normalize(quote)[:400]
    p = _normalize(page_text)
    if not q or not p:
        return 0.0
    if q[:120] in p or q[-120:] in p:
        return 1.0
    # sliding window over the page for best local similarity
    q_tokens = q.split()
    window = max(len(q_tokens), 40)
    p_tokens = p.split()
    best = 0.0
    step = max(window // 4, 1)
    for start in range(0, max(len(p_tokens) - window, 1), step):
        candidate = " ".join(p_tokens[start : start + window])
        ratio = difflib.SequenceMatcher(None, q[:300], candidate[:300]).ratio()
        best = max(best, ratio)
        if best >= 0.95:
            break
    return best


def extract_cited_urls(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in _URL_RE.findall(text):
        u = u.rstrip(".,;:")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def check_url(
    client: httpx.AsyncClient, url: str, quote: str | None = None,
    timeout: float = 12.0,
) -> SourceCheck:
    key = f"{url}::{hashlib_sha(quote or '')}"
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]
    try:
        resp = await client.get(url, follow_redirects=True, timeout=timeout)
        if resp.status_code == 200:
            match = None
            if quote:
                ctype = resp.headers.get("content-type", "")
                body = resp.text if "html" in ctype or "text" in ctype else ""
                if body:
                    match = _quote_ratio(quote, body)
                    status = "verified" if match >= 0.62 else ("exists" if match > 0 else "exists")
                else:
                    status = "exists"
                    match = None
            else:
                status = "exists"
            result = SourceCheck(url, status, resp.status_code, match,
                                 "" if status != "verified" else "quote matched on page")
        elif resp.status_code in (404, 410):
            result = SourceCheck(url, "dead", resp.status_code, None, "page not found")
        elif resp.status_code in (401, 403):
            result = SourceCheck(url, "unverified", resp.status_code, None,
                                 "paywall or bot protection — verify manually")
        else:
            result = SourceCheck(url, "unverified", resp.status_code, None,
                                 f"HTTP {resp.status_code}")
    except (httpx.HTTPError, OSError) as exc:
        result = SourceCheck(url, "unverified", None, None, f"network error: {type(exc).__name__}")
    _CACHE[key] = (now, result)
    return result


def hashlib_sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def verify_sources_exist(
    document_text: str,
    sources: list[dict],
    check_quotes: bool = False,
    enabled: bool = True,
    timeout: float = 12.0,
) -> list[dict]:
    """Verify every cited URL from both the document text and the source list."""
    urls = extract_cited_urls(document_text)
    for s in sources:
        u = s.get("url") or ""
        if u and u not in urls:
            urls.append(u)

    if not urls:
        return []
    if not enabled:
        return [SourceCheck(u, "unverified", None, None, "source checking disabled").as_dict()
                for u in urls]

    snippets = {s.get("url"): s.get("snippet", "") for s in sources}
    headers = {"User-Agent": "CounselAI/1.0 (+citation verification)"}
    async with httpx.AsyncClient(headers=headers) as client:
        checks = await asyncio.gather(*(
            check_url(client, u,
                      quote=snippets.get(u) if check_quotes else None,
                      timeout=timeout)
            for u in urls
        ))
    ordered = sorted(checks, key=lambda c: (c.status != "dead", c.url))
    return [c.as_dict() for c in ordered]


# ------------------------------------------------------------------ summary


def summarize_source_checks(checks: list[dict]) -> dict:
    counts: dict[str, int] = {"verified": 0, "exists": 0, "unverified": 0, "dead": 0}
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    dead = counts["dead"]
    total = sum(counts.values())
    status = "fail" if dead else ("warn" if counts["unverified"] else "pass")
    return {"total": total, "counts": counts, "status": status}
