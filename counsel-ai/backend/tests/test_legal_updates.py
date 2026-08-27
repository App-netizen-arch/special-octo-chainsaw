"""Unit tests — legal update filtering, doc-type classification, dedup."""

from __future__ import annotations

from app.services.legal_updates import (
    classify_doc_type,
    content_hash,
    passes_filters,
    score_relevance,
)


def _item(title="New California privacy regulations issued",
          jurisdiction="California", summary="Rules for businesses."):
    return {"title": title, "url": "https://oag.ca.gov/news/x",
            "jurisdiction": jurisdiction, "doc_type": classify_doc_type(title),
            "summary": summary, "published_at": 0}


def test_classify_legislation():
    assert classify_doc_type("Employment Rights Act 1996 amended") == "legislation"


def test_classify_case_law():
    assert classify_doc_type("Supreme Court judgment on arbitration clauses") == "case_law"


def test_classify_regulation():
    assert classify_doc_type("New rules for e-filing published") == "regulation"


def test_jurisdiction_filter_blocks_foreign():
    item = _item(jurisdiction="India")
    assert not passes_filters(item, ["California"], [])


def test_relevance_threshold():
    item = _item()
    item["relevance"] = score_relevance(item, ["privacy"])
    assert item["relevance"] >= 0.4
    assert passes_filters(item, ["California"], ["privacy"])


def test_irrelevant_practice_areas_lower_score():
    item = _item()
    low = score_relevance(item, ["maritime law", "admiralty"])
    high = score_relevance(item, ["privacy"])
    assert high > low


def test_content_hash_stable_and_sensitive():
    h1 = content_hash("Title A", "https://x.gov/1")
    h2 = content_hash("Title A", "https://x.gov/1")
    h3 = content_hash("Title B", "https://x.gov/1")
    assert h1 == h2 and h1 != h3
