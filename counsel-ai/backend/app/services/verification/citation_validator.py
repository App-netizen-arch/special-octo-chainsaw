"""Citation format validation — Bluebook & OSCOLA parsers.

Deterministic regex grammar for the citation families legal documents use:

* US cases:        ``Roe v. Wade, 410 U.S. 113 (1973)``
* US statutes:     ``42 U.S.C. § 1983`` / ``8 C.F.R. § 1003.2``
* Federal courts:  ``554 F.3d 850`` / ``112 S. Ct. 2727``
* UK/OSCOLA cases: ``[2020] EWCA Civ 1``, ``[1998] AC 750``, ``Donoghue v Stevenson [1932] AC 562``
* UK statutes:     ``Employment Rights Act 1996, s 94``
* Law reviews:     ``Author, Title, 115 Harv. L. Rev. 1234 (2002)``

``validate_citations(text)`` extracts every candidate citation and classifies
it as valid / malformed / unknown-format with a human-readable reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CitationCheck:
    raw: str
    kind: str          # case|statute|secondary|unknown
    style: str         # bluebook|oscola|unknown
    status: str        # valid|malformed
    reason: str = ""


# ------------------------------------------------------------------ patterns

_CONN = r"(?:of|and|the|ex|rel\.|v)"

US_CASE_RE = re.compile(
    r"\b(?P<party>[A-Z][A-Za-z.'\-]+(?:\s+(?:[A-Z][A-Za-z.'\-]+|" + _CONN + "))*"
    r"\s+v\.?\s+[A-Z][A-Za-z.'\-]+(?:\s+(?:[A-Z][A-Za-z.'\-]+|" + _CONN + "))*)"
    r",?\s+(?P<vol>\d{1,4})\s+"
    r"(?P<rep>(?:[A-Z][\w.]{0,12}|[A-Za-z]\.\d[a-z]*)(?:\s+(?:[A-Z][\w.]{0,12}|[A-Za-z]\.\d[a-z]*)){0,2})"
    r"\s+(?P<page>\d{1,5})"
    r"(?:\s*\((?P<extra>[^)]*?)(?P<year>\d{4})\))?"
)

US_STATUTE_RE = re.compile(
    r"\b\d{1,3}\s+U\.S\.C\.?\s*(?:§+|Sec\.?)\s*\d+[a-z0-9\-]*(?:\([a-z0-9ivx]+\))*"
    r"|\b\d{1,3}\s+C\.F\.R\.?\s*(?:§+)?\s*\d+\.\d+[a-z0-9\-]*"
    r"|\bCal\.\s+(?:Civ\.|Penal|Prob\.|Bus\.|\& Prof\.)?\s*Code\s*(?:§+)?\s*\d+[a-z0-9.\-()]*"
)

UK_CASE_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s+(?:EWCA|EWHCR|EWCA Civ|EWHC|UKSC|UKHL)\s+(?:Civ\s+|Ch\s+|Admin\s+)?(?P<num>\d{1,5})"
    r"|\[(?P<year2>\d{4})\]\s+(?:AC|QB|Ch|All ER| Fam)\s+(?P<page>\d{1,5})"
    r"|\b\d{1,4}\s+WLR\s+\d+",
    re.IGNORECASE,
)

UK_STATUTE_RE = re.compile(
    r"\b[A-Z][A-Za-z\s]+(?:Act|Measure)\s+(\d{4})(?:,\s*c(?:lause)?\.?\s*\d+)?"
    r"|(?:\bs\s*\d{1,3}[A-Z]?\b\s+of\s+the\s+[A-Z][A-Za-z\s]+Act\s+\d{4})"
)

SECONDARY_RE = re.compile(
    r"\b\d{1,3}\s+(?:Harv\.|Yale|Stanf\.|Chi\.|Colo\.|Tex\.|N\.Y\.U?\.|Mich\.|Va\.)\s*L(\.|aw)\s*(Rev\.)?\s*\d+",
)

_IN_TEXT_URL_RE = re.compile(r"https?://[^\s)>\"']+")


def extract_citations(text: str) -> list[str]:
    """Pull every recognizable citation string from a document."""
    found: list[str] = []
    for rx in (US_CASE_RE, US_STATUTE_RE, UK_CASE_RE, UK_STATUTE_RE, SECONDARY_RE):
        for m in rx.finditer(text):
            raw = re.sub(r"\s+", " ", m.group(0)).strip(" ,.;")
            if raw and raw not in found:
                found.append(raw)
    return found


def _classify(raw: str) -> CitationCheck:
    if US_STATUTE_RE.search(raw):
        return CitationCheck(raw, "statute", "bluebook", "valid")
    if UK_STATUTE_RE.search(raw):
        return CitationCheck(raw, "statute", "oscola", "valid")
    if UK_CASE_RE.search(raw):
        m = UK_CASE_RE.search(raw)
        # neutral citations need a court + number: already enforced by pattern.
        return CitationCheck(raw, "case", "oscola", "valid")
    if SECONDARY_RE.search(raw):
        return CitationCheck(raw, "secondary", "bluebook", "valid")
    m = US_CASE_RE.search(raw)
    if m:
        year = m.group("year")
        rep = (m.group("rep") or "").strip()
        page = m.group("page")
        issues: list[str] = []
        if not year:
            issues.append("missing year parenthesis")
        if len(rep.split()) > 4:
            issues.append(f"unrecognized reporter '{rep}'")
        if page == "0":
            issues.append("implausible first page 0")
        if issues:
            return CitationCheck(raw, "case", "bluebook", "malformed", "; ".join(issues))
        return CitationCheck(raw, "case", "bluebook", "valid")
    return CitationCheck(raw, "unknown", "unknown", "malformed", "not a recognized citation format")


def validate_citations(text: str) -> dict:
    """Full report used by the verification orchestrator."""
    checks: list[CitationCheck] = [_classify(c) for c in extract_citations(text)]
    valid = sum(1 for c in checks if c.status == "valid")
    malformed = [c for c in checks if c.status != "valid"]
    urls = _IN_TEXT_URL_RE.findall(text)
    return {
        "total": len(checks),
        "valid": valid,
        "malformed": [
            {"citation": c.raw, "kind": c.kind, "style": c.style, "reason": c.reason}
            for c in malformed[:20]
        ],
        "urls_found": len(urls),
        "styles_detected": sorted({c.style for c in checks if c.style != "unknown"}),
        "status": "pass" if not malformed or valid >= max(1, int(0.7 * len(checks))) else "warn",
    }


# --------------------------------------------------------------- normalizing


def normalize_case_name(name: str) -> str:
    """'ROE V. WADE' / 'Roe  v.  Wade' -> 'Roe v. Wade' for dedup keys."""
    n = re.sub(r"\s+", " ", name.strip())
    return re.sub(r"\s+v\.?\s+", " v. ", n)
