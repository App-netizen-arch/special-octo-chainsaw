"""Web search client with legitimate-source-only enforcement.

Adapted from Perplexica/Vane's SearXNG integration (MIT): results normalized
as {title,url,content}, ranked/deduped by cosine similarity over hashed
bag-of-words vectors (keep >0.5 vs query, drop >0.75 vs kept items).
Tavily is a drop-in provider reusing its own scoring.

Every result passes ``utils.domain_whitelist.is_legitimate_source`` BEFORE it
can reach any LLM or the UI. Provider calls are audited as external
transmissions and counted in metrics.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Optional

import httpx

from ..config import settings
from ..database import record_audit
from ..utils.domain_whitelist import filter_results
from ..utils.logging_setup import new_correlation_id
from ..utils.metrics import inc

log = logging.getLogger("counsel.search")

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
STOPWORDS = frozenset(
    "the a an and or of to in on for with by from as at is are was were be been it its this that".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def _embed(text: str, dim: int = 512) -> dict[int, float]:
    vec: dict[int, float] = {}
    for tok in _tokens(text)[:256]:
        h = hash(tok) % dim
        vec[h] = vec.get(h, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def cosine(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def rank_and_dedupe(query: str, results: list[dict], cap: int = 20) -> list[dict]:
    """Vane thresholds: keep sim>0.5, greedy-dedup at 0.75, cap 20."""
    qv = _embed(query)
    scored: list[tuple[float, int, dict]] = []
    for i, r in enumerate(results):
        text = r.get("content") or r.get("title") or ""
        sim = cosine(qv, _embed(text))
        if sim <= 0.5 and r.get("score") is None:
            continue
        score = float(r.get("score") or sim)
        scored.append((score, i, r))
    scored.sort(key=lambda t: (-t[0], t[1]))
    kept: list[dict] = []
    kept_vecs: list[dict[int, float]] = []
    for score, _, r in scored:
        rv = _embed((r.get("content") or "") + " " + (r.get("title") or ""))
        if any(cosine(rv, kv) > 0.75 for kv in kept_vecs):
            continue
        r["relevance"] = round(score, 4)
        kept.append(r)
        kept_vecs.append(rv)
        if len(kept) >= cap:
            break
    return kept


# ------------------------------------------------------------------ providers


async def search_searxng(query: str, max_results: int = 10) -> list[dict]:
    url = settings.searxng_url.rstrip("/") + "/search"
    params: dict[str, Any] = {"q": query, "format": "json"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    out = []
    for r in data.get("results", [])[: max_results * 2]:
        out.append(
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content") or r.get("title", ""),
            }
        )
    return out


async def search_tavily(query: str, max_results: int = 10) -> list[dict]:
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY not set")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": False,
                "max_results": max_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score"),
        }
        for r in data.get("results", [])
    ]


async def web_search(
    query: str, max_results: int = 8, provider: Optional[str] = None,
    user_id: str | None = None,
) -> tuple[list[dict], str]:
    """Returns (filtered+ranked results, provider-used).

    Raises RuntimeError with a user-friendly message when no provider works.
    Every successful provider call lands in the audit trail.
    """
    order = [provider] if provider else (
        ["auto"] if settings.search_provider == "auto" else [settings.search_provider, "auto"]
    )
    errors: list[str] = []
    cid = new_correlation_id()
    for prov in order:
        try:
            raw: list[dict] | None = None
            used: str | None = None
            if prov in ("tavily", "auto") and settings.tavily_api_key:
                raw = await search_tavily(query, max_results)
                used = "tavily"
            elif prov in ("searxng", "auto"):
                raw = await search_searxng(query, max_results)
                used = "searxng"
            elif prov == "tavily":
                errors.append("tavily: no API key")
                continue
            if raw is None or used is None:
                continue
            filtered = filter_results(raw)
            record_audit(user_id, f"search.{used}_call", target=query[:200],
                         detail={"raw": len(raw), "whitelisted": len(filtered)},
                         correlation_id=cid)
            inc("search.queries", labels={"provider": used})
            if raw and not filtered:
                raise RuntimeError("all results outside legitimate-source whitelist")
            return rank_and_dedupe(query, filtered, cap=max_results), used
        except RuntimeError as exc:
            errors.append(f"{prov}: {exc}")
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("provider %s failed: %s", prov, exc)
            errors.append(f"{prov}: unreachable")
    raise RuntimeError(_no_provider_msg(errors))


def _no_provider_msg(errors: list[str]) -> str:
    return (
        "No legal search provider is available right now. Configure either a "
        "Tavily API key (Settings/.env) or start the bundled SearXNG container "
        "(docker compose up searxng). Details: " + "; ".join(errors)
    )


def keywords(query: str, n: int = 6) -> list[str]:
    common = Counter(_tokens(query))
    return [w for w, _ in common.most_common(n)]
