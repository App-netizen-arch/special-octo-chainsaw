"""Clause structure rule engine.

Enforces that a generated document of a known type contains the sections the
practice expects (e.g. an NDA must define Confidential Information, Term and
Exclusions), flags leftover drafting placeholders, missing signature blocks
and missing governing-law clauses.

Rules are declarative so firms can extend them via admin settings without
touching code.
"""

from __future__ import annotations

import re

# heading -> list of acceptable regexes (any match satisfies the requirement)
DOC_RULES: dict[str, dict] = {
    "nda": {
        "label": "Non-Disclosure Agreement",
        "required_sections": [
            {"name": "Confidentiality / Confidential Information", "pattern": r"(?i)#{1,3}.*confidential"},
            {"name": "Term", "pattern": r"(?i)#{1,3}.*\bterm\b"},
            {"name": "Exclusions / Carve-outs", "pattern": r"(?i)#{1,3}.*(exclusion|carve.?out|not include)"},
            {"name": "Obligations", "pattern": r"(?i)#{1,3}.*(obligation|use of|duties)"},
            {"name": "Governing Law", "pattern": r"(?i)#{1,3}.*(governing law|governed by)"},
        ],
        "requires_signature_block": True,
    },
    "employment_contract": {
        "label": "Employment Contract",
        "required_sections": [
            {"name": "Position / Duties", "pattern": r"(?i)#{1,3}.*(position|duties|role)"},
            {"name": "Remuneration", "pattern": r"(?i)#{1,3}.*(remunerat|salary|compensation)"},
            {"name": "Termination", "pattern": r"(?i)#{1,3}.*terminat"},
            {"name": "Confidentiality", "pattern": r"(?i)#{1,3}.*confidential"},
            {"name": "Governing Law", "pattern": r"(?i)#{1,3}.*(governing law|governed by)"},
        ],
        "requires_signature_block": True,
    },
    "legal_memo": {
        "label": "Legal Memorandum",
        "required_sections": [
            {"name": "Question Presented", "pattern": r"(?i)#{1,3}.*(question presented|issue)"},
            {"name": "Brief Answer", "pattern": r"(?i)#{1,3}.*(brief answer|short answer)"},
            {"name": "Facts", "pattern": r"(?i)#{1,3}.*facts?"},
            {"name": "Discussion", "pattern": r"(?i)#{1,3}.*(discussion|analysis)"},
            {"name": "Conclusion", "pattern": r"(?i)#{1,3}.*conclusion"},
        ],
        "requires_signature_block": False,
    },
    "motion": {
        "label": "Court Motion",
        "required_sections": [
            {"name": "Introduction / Relief", "pattern": r"(?i)#{1,3}.*(introduction|relief|movant)"},
            {"name": "Background", "pattern": r"(?i)#{1,3}.*background"},
            {"name": "Argument", "pattern": r"(?i)#{1,3}.*argument"},
        ],
        "requires_signature_block": True,
    },
    "letter": {
        "label": "Formal Letter",
        "required_sections": [],
        "requires_signature_block": True,
    },
    "general": {
        "label": "General document",
        "required_sections": [
            {"name": "Governing Law (recommended)", "pattern": r"(?i)(governing law|governed by)"},
        ],
        "requires_signature_block": False,
    },
}

PLACEHOLDER_PATTERNS = (
    ("blank underscore run", re.compile(r"_{4,}")),
    ("TODO marker", re.compile(r"\bTODO\b|\bTBD\b|\bXXX\b")),
    ("angle placeholder", re.compile(r"<[A-Z][A-Z\s]{4,}>")),
)

DISCLAIMER_RE = re.compile(r"(?i)(not (?:a substitute for|legal advice)|for review only|reviewed by a qualified)")


def detect_doc_type(text: str) -> str:
    t = text.lower()
    if "non-disclosure agreement" in t or re.search(r"\bnda\b", t):
        return "nda"
    if "employment contract" in t or ("employer" in t and "employee" in t and "# employment" in t):
        return "employment_contract"
    if "legal memorandum" in t or "memorandum" in t:
        return "legal_memo"
    if re.search(r"\bmotion\b", t):
        return "motion"
    if "yours faithfully" in t or "yours sincerely" in t:
        return "letter"
    return "general"


def check_clauses(document: str, doc_type: str | None = None) -> dict:
    """Run the rule set. Returns issues + status consumed by the orchestrator."""
    doc_type = doc_type or detect_doc_type(document)
    rules = DOC_RULES.get(doc_type, DOC_RULES["general"])

    issues: list[dict] = []

    for req in rules["required_sections"]:
        if not re.search(req["pattern"], document):
            issues.append({
                "severity": "high",
                "code": "missing_section",
                "message": f"{rules['label']} is missing a required section: {req['name']}.",
                "section": req["name"],
            })

    if rules["requires_signature_block"]:
        has_sig = bool(re.search(
            r"(?i)(signature[s]?\s*(block|table)?|signed|sign here|______{2,}|respectfully submitted)",
            document))
        if not has_sig:
            issues.append({
                "severity": "high",
                "code": "missing_signature",
                "message": f"No signature block detected — {rules['label']} must be executable.",
            })

    placeholders = []
    for label, rx in PLACEHOLDER_PATTERNS:
        n = len(rx.findall(document))
        if n:
            placeholders.append({"kind": label, "count": n})
    if placeholders:
        issues.append({
            "severity": "info",
            "code": "placeholders_present",
            "message": (
                f"{sum(p['count'] for p in placeholders)} drafting placeholder(s) remain — "
                "confirm every blank is intentional before sending."
            ),
            "detail": placeholders,
        })

    if not DISCLAIMER_RE.search(document):
        issues.append({
            "severity": "medium",
            "code": "missing_disclaimer",
            "message": "Draft-review disclaimer not found; every generated document must state it is not legal advice.",
        })

    severity_rank = {"high": 0, "medium": 1, "info": 2}
    issues.sort(key=lambda i: severity_rank[i["severity"]])
    blocking = [i for i in issues if i["severity"] == "high"]
    return {
        "doc_type": doc_type,
        "status": "fail" if blocking else ("warn" if issues else "pass"),
        "issues": issues,
    }
