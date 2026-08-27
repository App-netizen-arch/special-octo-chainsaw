"""Multi-agent verification orchestrator.

Flow for generated documents:

1. **Writer Agent** (LLM) — produces the MDX document upstream.
2. **Symbolic Verification Layer** (deterministic) — citation format, source
   existence, clause structure, PII scan, jurisdiction consistency.
3. **Reviewer Agent** (LLM) — turns the raw report into a plain-English
   explanation with concrete next steps; never alters the document itself.
4. **Skills Compliance** (LLM + deterministic) — checks the draft against the
   user's active skills' required sections/tone/citation style.
5. **Privacy Auditor** (deterministic) — confidential-client leak screen.

Chat and research modes run only the lightweight subset (source existence +
PII) — see ``verify_light``.

The returned report is JSON-shaped exactly as ``VerificationReport`` in the
Flutter client expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from ...database import record_audit
from ...utils.metrics import inc
from .citation_validator import validate_citations
from .clause_rules import check_clauses, detect_doc_type
from .jurisdiction_checker import check_jurisdiction
from .pii_detector import privacy_audit
from .source_existence import summarize_source_checks, verify_sources_exist

log = logging.getLogger("counsel.verify")

REVIEWER_SYSTEM = (
    "You are the Reviewer Agent inside Counsel AI's verification pipeline. "
    "You receive a deterministic verification report about a legal draft. "
    "Explain every issue in one or two plain-English sentences for a busy "
    "lawyer, ordered by severity, then give a single 'Bottom line' sentence "
    "on whether the draft is safe to proceed to human review. Never rewrite "
    "the document. No emojis."
)

SKILLS_COMPLIANCE_PROMPT = (
    "You are the Skills Compliance Agent. Compare this legal draft against the "
    "active skill requirements below and answer with a short checklist: each "
    "requirement followed by MET / NOT MET / PARTIAL plus a one-line reason.\n\n"
    "Skill requirements:\n\"\"\"\n{requirements}\n\"\"\"\n\nDraft:\n\"\"\"\n{draft}\n\"\"\"\n"
)


async def verify_document(
    document_md: str,
    *,
    jurisdiction: dict[str, str] | None = None,
    doc_type: str | None = None,
    sources: list[dict] | None = None,
    skills: list[dict[str, Any]] | None = None,
    client_names: list[str] | None = None,
    check_sources_http: bool = True,
    source_timeout: float = 12.0,
    llm_mode: str = "api",
    api_key: str | None = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Full battery. Returns {status, checks:{...}, review, skills_compliance,
    privacy, summary}."""
    from ..llm import complete

    jurisdiction = jurisdiction or {}
    sources = sources or []
    doc_type = doc_type or detect_doc_type(document_md)

    # ---- step 2: symbolic layer ------------------------------------------
    citations = validate_citations(document_md)
    existence = await verify_sources_exist(
        document_md, sources, check_quotes=True,
        enabled=check_sources_http, timeout=source_timeout,
    )
    clauses = check_clauses(document_md, doc_type=doc_type)
    pii = detect_pii_scan(document_md, client_names)
    juris = check_jurisdiction(document_md,
                               province=jurisdiction.get("province", ""),
                               country=jurisdiction.get("country", ""))

    source_summary = summarize_source_checks(existence)
    checks = {
        "citation_format": citations,
        "source_existence": {"checks": existence, **source_summary},
        "clause_structure": clauses,
        "jurisdiction": juris,
        "pii": pii["pii"],
    }

    # ---- steps 3-4: LLM agents -------------------------------------------
    review_text = ""
    try:
        review_text = await complete(
            [
                {"role": "system", "content": REVIEWER_SYSTEM},
                {"role": "user", "content": json.dumps(checks, default=str)[:6000]},
            ],
            mode=llm_mode, api_key=api_key, max_tokens=700, user_id=user_id,
        )
    except Exception as exc:  # noqa: BLE001 — reviewer is best-effort
        log.warning("reviewer agent failed: %s", exc)
        review_text = _fallback_review(checks)

    skills_compliance = await verify_skills_compliance(
        document_md, skills or [], llm_mode=llm_mode, api_key=api_key, user_id=user_id,
    )

    overall_status = _overall_status(checks, skills_compliance)
    record_audit(user_id, "verification.document", target=doc_type,
                 detail={"overall": overall_status})
    inc("verification.runs", labels={"outcome": overall_status})

    return {
        "level": "document",
        "doc_type": doc_type,
        "status": overall_status,
        "checks": checks,
        "privacy": pii,
        "skills_compliance": skills_compliance,
        "review": review_text.strip(),
        "summary": {
            "issues_total": sum(len(c.get("issues", [])) for c in (
                clauses, juris)),
            "citations_valid": citations["valid"],
            "citations_total": citations["total"],
            "sources_dead": source_summary["counts"].get("dead", 0),
        },
    }


def detect_pii_scan(document: str, client_names: list[str] | None) -> dict:
    from .pii_detector import privacy_audit

    return privacy_audit(document, client_names)


async def verify_skills_compliance(
    document: str,
    skills: list[dict[str, Any]],
    llm_mode: str = "api",
    api_key: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Deterministic requirement extraction + LLM compliance checklist."""
    if not skills:
        return {"applicable": False, "status": "pass", "checklist": ""}
    from ..llm import complete

    requirements: list[str] = []
    for s in skills:
        req = f"Skill '{s['name']}': {s.get('description', '')}"
        if s.get("citation_style"):
            req += f"; use {s['citation_style']} citation style"
        triggers = s.get("triggers") or []
        if triggers:
            req += f"; must address: {', '.join(str(t) for t in triggers[:6])}"
        if s.get("system_prompt"):
            req += f"\nInstructions: {s['system_prompt'][:500]}"
        requirements.append(req)

    checklist = ""
    try:
        checklist = await complete(
            [{"role": "user", "content": SKILLS_COMPLIANCE_PROMPT.format(
                requirements="\n".join(requirements), draft=document[:6000])}],
            mode=llm_mode, api_key=api_key, max_tokens=600, user_id=user_id,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("skills compliance agent failed: %s", exc)
        checklist = "Automated skills compliance could not run; verify manually."
    unmet = checklist.upper().count("NOT MET")
    partial = checklist.upper().count("PARTIAL")
    status = "fail" if unmet else ("warn" if partial else "pass")
    return {"applicable": True, "status": status, "checklist": checklist.strip()}


async def verify_light_async(
    text: str, sources: list[dict], *, enabled: bool = True, timeout: float = 12.0,
    include_names: bool = True,
) -> dict[str, Any]:
    """Lightweight checks for chat/research answers."""
    from .pii_detector import detect_pii

    existence = await verify_sources_exist(text, sources, check_quotes=False,
                                           enabled=enabled, timeout=timeout)
    summary = summarize_source_checks(existence)
    return {
        "level": "light",
        "status": summary["status"],
        "checks": {"source_existence": {"checks": existence, **summary},
                   "pii": detect_pii(text, include_names=include_names)},
        "review": "",
    }


def _fallback_review(checks: dict[str, Any]) -> str:
    lines: list[str] = []
    for name, block in checks.items():
        status = block.get("status")
        if status in ("pass", None):
            continue
        lines.append(f"- {name.replace('_', ' ').title()}: {status}.")
        for issue in block.get("issues", [])[:3]:
            lines.append(f"  - {issue['message']}")
        for malformed in block.get("malformed", [])[:3]:
            lines.append(f"  - Citation issue: {malformed['citation']} ({malformed['reason']})")
        dead = [c for c in block.get("checks", []) if isinstance(c, dict) and c.get("status") == "dead"]
        for d in dead[:3]:
            lines.append(f"  - Dead link: {d['url']}")
    if not lines:
        return "All automated checks passed. Proceed to human review."
    return "\n".join(lines) + "\n\nBottom line: resolve the flagged items before relying on this draft."


def _overall_status(checks: dict[str, Any], skills_compliance: dict[str, Any]) -> str:
    statuses = [block.get("status", "pass") for block in checks.values()]
    if skills_compliance.get("applicable"):
        statuses.append(skills_compliance.get("status", "pass"))
    if any(s == "fail" for s in statuses):
        return "fail"
    if any(s == "warn" for s in statuses):
        return "warn"
    return "pass"


# keep an alias matching the spec naming used by routers
orchestrate_document_verification = verify_document
