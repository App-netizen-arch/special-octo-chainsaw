"""Skills manager — user-created & built-in skill library.

A *skill* bundles: name, description, trigger conditions, system-prompt
instructions, example output, document type and citation style.

At every user query ``select_relevant_skills`` scores enabled skills against
the query and returns ONLY the relevant ones; their instructions are injected
into the system prompt by the chat pipeline (never all skills).

Built-ins are seeded on first run and are immutable; users create editable
copies (``fork_builtin``) or brand-new skills via the Skills Manager UI.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..database import list_skills, session_scope, uid, upsert_skill
from ..models.db import Skill

BUILT_IN_SKILLS: list[dict[str, Any]] = [
    {
        "builtin_key": "legal_memo_drafting",
        "name": "Legal Memo Drafting",
        "description": "Structures answers as an internal legal memorandum.",
        "triggers": ["memo", "memorandum", "advise on", "legal opinion"],
        "doc_type": "legal_memo",
        "citation_style": "bluebook",
        "system_prompt": (
            "Structure the answer as a legal memorandum with sections: Question "
            "Presented; Brief Answer; Facts; Discussion; Conclusion & "
            "Recommendations. Formal objective register."
        ),
        "example_output": "# LEGAL MEMORANDUM\n\n## Question Presented\n...",
    },
    {
        "builtin_key": "nda_drafting",
        "name": "NDA Drafting",
        "description": "Drafts mutual or one-way non-disclosure agreements.",
        "triggers": ["nda", "non-disclosure", "nondisclosure", "confidentiality agreement"],
        "doc_type": "nda",
        "citation_style": "",
        "system_prompt": (
            "Produce a complete NDA: parties block; Purpose; Confidential "
            "Information definition; Obligations of the Receiving Party; "
            "Exclusions; Term and Termination; Governing Law; signature table. "
            "Numbered headings; underscores for unknown facts."
        ),
        "example_output": "# MUTUAL NON-DISCLOSURE AGREEMENT\n\n## 1. Purpose\n...",
    },
    {
        "builtin_key": "bluebook_citation",
        "name": "Bluebook Citation",
        "description": "Formats all authorities in Bluebook style.",
        "triggers": ["bluebook", "cite this", "citation format", "authority"],
        "doc_type": "general",
        "citation_style": "bluebook",
        "system_prompt": (
            "Cite every authority in Bluebook format: cases as 'Name v. Name, "
            "Vol Reporter Page (Court Year)'; statutes as 'Title U.S.C. § sec'. "
            "Pinpoint pages where available."
        ),
        "example_output": "Roe v. Wade, 410 U.S. 113 (1973).",
    },
    {
        "builtin_key": "case_law_summary",
        "name": "Case Law Summary",
        "description": "Summarises case law into issue/holding/reasoning blocks.",
        "triggers": ["case law", "precedent", "holding", "ratio", "summarise the case", "summarize the case"],
        "doc_type": "general",
        "citation_style": "bluebook",
        "system_prompt": (
            "For each authority provide: Citation; Facts (2 lines); Issue; "
            "Holding; Reasoning (3 lines max); Practical Takeaway."
        ),
        "example_output": "**Donoghue v Stevenson [1932] AC 562**\n- Facts: ...",
    },
    {
        "builtin_key": "contract_review",
        "name": "Contract Review",
        "description": "Reviews contracts clause-by-clause with risk flags.",
        "triggers": ["review contract", "review this agreement", "redline", "risk clause", "clause review"],
        "doc_type": "general",
        "citation_style": "",
        "system_prompt": (
            "Review clause-by-clause. For each clause state: what it does, risk "
            "level (LOW/MEDIUM/HIGH) for the client side, and a suggested "
            "revision. End with an overall risk summary table."
        ),
        "example_output": "| Clause | Risk | Suggested revision |\n|---|---|---|",
    },
]


def seed_builtin_skills() -> int:
    """Insert missing built-ins once. Returns number added."""
    added = 0
    with session_scope() as s:
        existing = {
            r.builtin_key for r in s.query(Skill).filter(Skill.builtin_key.isnot(None)).all()
        }
    for spec in BUILT_IN_SKILLS:
        if spec["builtin_key"] in existing:
            continue
        data = {**spec, "id": uid(16), "owner_id": None, "enabled": True,
                "triggers_json": json.dumps(spec["triggers"])}
        data.pop("triggers")
        upsert_skill(data)
        added += 1
    return added


def fork_builtin(skill_id: str, owner_id: str) -> dict[str, Any] | None:
    base = None
    from ..database import get_skill

    base = get_skill(skill_id)
    if base is None:
        return None
    copy = {k: v for k, v in base.items()}
    copy.pop("id")
    copy.pop("builtin_key", None)  # forks are user-owned, not built-ins
    copy["owner_id"] = owner_id
    copy["name"] = f"{base['name']} (my copy)"
    return upsert_skill({**copy, "id": uid(16)})


def select_relevant_skills(
    query: str,
    *,
    mode: str = "api",
    doc_type_hint: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Score enabled skills against the query; return only relevant ones.

    Scoring: +3 per trigger keyword present in the query, +2 when the skill's
    doc_type matches a detected drafting intent, +1 if the skill name appears.
    Skills scoring 0 are excluded entirely.
    """
    q = query.lower()
    scored: list[tuple[float, dict[str, Any]]] = []
    drafting_intent = bool(re.search(
        r"\b(draft|prepare|write|generate|review)\b.*\b(document|agreement|contract|memo|motion|letter|nda)\b", q))
    for s in list_skills():
        if not s.get("enabled", True):
            continue
        score = 0.0
        for trig in s.get("triggers") or []:
            t = str(trig).lower().strip()
            if t and t in q:
                score += 3.0
        if s.get("name", "").lower() in q:
            score += 1.0
        if drafting_intent and doc_type_hint and s.get("doc_type") == doc_type_hint:
            score += 2.0
        if mode == "research" and score < 6:
            # research mode keeps only strongly matching skills to stay focused
            continue
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda t: -t[0])
    return [s for _, s in scored[:limit]]


def skills_to_prompt_blocks(skills: list[dict[str, Any]]) -> list[str]:
    blocks: list[str] = []
    for s in skills:
        parts = [f"Skill '{s['name']}': {s.get('description','')}."]
        if s.get("system_prompt"):
            parts.append(s["system_prompt"])
        if s.get("citation_style"):
            parts.append(f"Use {s['citation_style']} citation style.")
        blocks.append(" ".join(p for p in parts if p))
    return blocks


def validate_skill_payload(data: dict[str, Any]) -> tuple[bool, str]:
    if not str(data.get("name") or "").strip():
        return False, "Skill name is required."
    triggers = data.get("triggers") or []
    if not isinstance(triggers, list) or not all(isinstance(t, str) for t in triggers):
        return False, "Triggers must be a list of strings."
    if len(json.dumps(data.get("system_prompt") or "")) > 20000:
        return False, "System prompt too long (max ~20k chars)."
    return True, ""
