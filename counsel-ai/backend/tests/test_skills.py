"""Unit tests — skills engine: seeding + trigger-based selection."""

from __future__ import annotations

from app.database import init_db, list_skills
from app.services.skills_manager import (
    select_relevant_skills,
    seed_builtin_skills,
    skills_to_prompt_blocks,
    validate_skill_payload,
)


def test_seed_builtins_once():
    init_db()
    seed_builtin_skills()   # idempotent: first call seeds, later calls no-op
    second = seed_builtin_skills()
    assert second == 0
    names = {s["name"] for s in list_skills()}
    assert {
        "Legal Memo Drafting", "NDA Drafting", "Bluebook Citation",
        "Case Law Summary", "Contract Review",
    } <= names


def test_selection_returns_only_relevant():
    hits = select_relevant_skills("Draft an NDA for a software pilot")
    assert len(hits) >= 1
    assert any(s["builtin_key"] == "nda_drafting" for s in hits)
    # unrelated skills must NOT be injected
    assert not any(s["builtin_key"] == "case_law_summary" and "holding" not in "draft an nda"
                   for s in hits)


def test_memo_trigger():
    hits = select_relevant_skills("Please prepare a memo on limitation periods")
    assert any(s["builtin_key"] == "legal_memo_drafting" for s in hits)


def test_no_match_returns_empty():
    hits = select_relevant_skills("What is the weather today?")
    assert hits == []


def test_prompt_blocks_include_citation_style():
    blocks = skills_to_prompt_blocks(
        [s for s in list_skills() if s.get("builtin_key") == "bluebook_citation"])
    assert blocks and "bluebook" in blocks[0].lower()


def test_validate_payload():
    ok, _ = validate_skill_payload({"name": "X", "triggers": ["a"], "system_prompt": "p"})
    assert ok
    bad, reason = validate_skill_payload({"name": "", "triggers": []})
    assert not bad and "name" in reason.lower()
