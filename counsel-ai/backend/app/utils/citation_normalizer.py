"""Citation normalization.

Every citation that reaches the Flutter app — whether it came from web search,
the research agent, or RAG over uploaded documents — passes through
`normalize()` so the client only ever deals with one JSON shape:

    {title, url, snippet, document_name, page, relevance, kind}

Provenance note: the in-text citation convention (`([Author](url))` plus a
deterministic `## References` appendix) follows gpt-researcher's report format
(Apache-2.0); page-level `[Document Name, Page X]` citations follow the MVP spec.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..models.schemas import Source


def normalize_web_result(raw: dict[str, Any]) -> Source:
    return Source(
        title=str(raw.get("title") or raw.get("url") or "Untitled source")[:300],
        url=str(raw.get("url") or ""),
        snippet=(str(raw.get("content") or raw.get("snippet") or ""))[:400],
        relevance=float(raw.get("score") or raw.get("relevance") or 0.0),
        kind="web",
    )


def normalize_document_hit(doc_name: str, page: int | None, snippet: str, score: float) -> Source:
    return Source(
        title=doc_name,
        url="",
        snippet=snippet[:400],
        document_name=doc_name,
        page=page,
        relevance=round(float(score), 4),
        kind="document",
    )


def normalize_all(items: Iterable[dict[str, Any]], default_kind: str = "web") -> list[Source]:
    out: list[Source] = []
    for item in items:
        kind = item.get("kind", default_kind)
        try:
            if kind == "document":
                out.append(
                    normalize_document_hit(
                        item.get("document_name") or item.get("name", ""),
                        item.get("page"),
                        item.get("snippet", ""),
                        float(item.get("relevance", item.get("score", 0.0))),
                    )
                )
            else:
                out.append(normalize_web_result(item))
        except (TypeError, ValueError):
            continue
    # de-duplicate by url (web) or doc+page (documents), keep highest score
    best: dict[str, Source] = {}
    for s in out:
        key = s.url if s.kind == "web" else f"{s.document_name}#p{s.page}"
        if key not in best or s.relevance > best[key].relevance:
            best[key] = s
    ranked = sorted(best.values(), key=lambda s: -s.relevance)
    return ranked


def references_appendix(sources: list[Source]) -> str:
    """Deterministic '## References' markdown block (gpt-researcher style)."""
    lines: list[str] = ["", "## References"]
    for i, s in enumerate(sources, start=1):
        label = s.title or s.document_name or s.url
        if s.kind == "document":
            loc = f", Page {s.page}" if s.page else ""
            lines.append(f"{i}. [{label}{loc}] (uploaded document)")
        elif s.url:
            lines.append(f"{i}. [{label}]({s.url})")
        else:
            lines.append(f"{i}. {label}")
    return "\n".join(lines)


def parse_in_text_urls(markdown: str) -> list[str]:
    """Extract URLs the model actually cited in-text, in order of appearance."""
    urls: list[str] = []
    for chunk in markdown.split("]("):
        if "(" in chunk:
            candidate = chunk.rsplit("(", 1)[-1].split(")")[0]
            if candidate.startswith("http"):
                urls.append(candidate)
    seen: set[str] = set()
    ordered = [u for u in urls if not (u in seen or seen.add(u))]
    return ordered
