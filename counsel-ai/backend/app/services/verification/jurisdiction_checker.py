"""Jurisdiction rule checking.

Deterministically verifies that a document's legal references are consistent
with the user's jurisdiction:

1. **Presence** — a jurisdiction-specific document should reference its
   governing jurisdiction at least once (statute, court, or explicit
   "governed by" clause).
2. **Conflict** — flags references to *other* jurisdictions' law (a California
   NDA citing New York statutes is almost always an error).
3. **Court hints** — known court names are matched to their jurisdictions.
"""

from __future__ import annotations

import re

# jurisdiction -> markers that indicate ITS law governs
JURISDICTION_MARKERS: dict[str, tuple[str, ...]] = {
    "California": ("california", r"cal\.", "9th cir", r"civ\. code", r"cal\. bus", "san francisco", "los angeles"),
    "New York": ("new york", r"n\.y\.", "2d cir", "nyc", "deliberate indifference"),
    "Texas": ("texas", r"tex\.", "5th cir", "houston", "dallas"),
    "Florida": ("florida", r"fla\.", "11th cir", "miami"),
    "Illinois": ("illinois", r"ill\.", "7th cir", "chicago"),
    "Washington": ("washington state", r"wash\.", "9th cir", "seattle"),
    "Massachusetts": ("massachusetts", r"mass\.", "1st cir", "boston"),
    "Delaware": ("delaware", r"del\.", "court of chancery"),
    "Georgia": ("georgia", r"ga\.", "atlanta"),
    "Virginia": ("virginia", r"va\.", "4th cir"),
    # countries / provinces
    "England": ("england and wales", "english law", "ewca", "ewhc", "uksc"),
    "Scotland": ("scotland", "scots law", "outer house"),
    "Wales": ("wales", "welsh"),
    "Northern Ireland": ("northern ireland", "belfast"),
    "Ontario": ("ontario", "canlii", "onca"),
    "Quebec": ("quebec", "civil code of qué?bec"),
    "British Columbia": ("british columbia", "bcca", "vancouver"),
    "Alberta": ("alberta", "abca", "calgary", "edmonton"),
    "Manitoba": ("manitoba", "mbca", "winnipeg"),
    "Maharashtra": ("maharashtra", "bombay high court", "mumbai"),
    "Delhi NCT": ("delhi", "delhi high court"),
    "Karnataka": ("karnataka", "karnataka high court", "bangalore", "bengaluru"),
    "Tamil Nadu": ("tamil nadu", "madras high court", "chennai"),
    "Uttar Pradesh": ("uttar pradesh", "allahabad high court"),
    "West Bengal": ("west bengal", "calcutta high court", "kolkata"),
    "New South Wales": ("new south wales", "nsw", "nswca"),
    "Victoria": ("victoria", "vsc", "melbourne"),
    "Queensland": ("queensland", "qsc", "brisbane"),
    "Western Australia": ("western australia", "wasc", "perth"),
    "Berlin": ("berlin", "germany"),
    "Bavaria": ("bavaria", "bayern", "munich"),
    "Hesse": ("hesse", "frankfurt"),
    "North Rhine-Westphalia": ("north rhine-westphalia", "nrw", "düsseldorf|dusseldorf"),
}

COUNTRY_OF: dict[str, str] = {
    **{s: "United States" for s in (
        "California", "New York", "Texas", "Florida", "Illinois",
        "Washington", "Massachusetts", "Delaware", "Georgia", "Virginia")},
    **{s: "United Kingdom" for s in ("England", "Scotland", "Wales", "Northern Ireland")},
    **{s: "Canada" for s in ("Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba")},
    **{s: "India" for s in ("Maharashtra", "Delhi NCT", "Karnataka", "Tamil Nadu",
                            "Uttar Pradesh", "West Bengal")},
    **{s: "Australia" for s in ("New South Wales", "Victoria", "Queensland", "Western Australia")},
    **{s: "Germany" for s in ("Berlin", "Bavaria", "Hesse", "North Rhine-Westphalia")},
}

GOVERNING_LAW_RE = re.compile(
    r"(?i)(?:govern(?:ed|ing)\s+(?:by|the laws of)|laws of|law of)[^.\n]{0,120}"
)


def _marker_hits(text: str, markers: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    hits = []
    for m in markers:
        if re.search(m, lowered):
            hits.append(m)
    return hits


def _marker_occurrences(text: str, markers: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(len(re.findall(m, lowered)) for m in markers)


def check_jurisdiction(document: str, province: str = "", country: str = "") -> dict:
    """Return deterministic jurisdiction consistency report."""
    issues: list[dict] = []
    target = province or country
    governing = GOVERNING_LAW_RE.findall(document)

    own_hits = _marker_hits(document, JURISDICTION_MARKERS.get(province, ()))
    if not own_hits:
        own_hits = _marker_hits(document, JURISDICTION_MARKERS.get(country, ()))

    if target and not own_hits:
        issues.append({
            "severity": "medium",
            "code": "jurisdiction_not_referenced",
            "message": (
                f"No reference to {target} law was found. If this draft should be "
                f"governed by another jurisdiction, state it explicitly; otherwise "
                f"add the {target} governing-law reference."
            ),
        })

    # conflicting jurisdictions: strong markers of OTHER jurisdictions present
    conflicts: list[str] = []
    for jur, markers in JURISDICTION_MARKERS.items():
        if jur == target:
            continue
        if _marker_occurrences(document, markers) >= 2:
            conflicts.append(jur)
    for jur in conflicts[:3]:
        issues.append({
            "severity": "high",
            "code": "conflicting_jurisdiction",
            "message": (
                f"Multiple references to {jur} law detected while the workspace "
                f"jurisdiction is {target}. Verify choice-of-law intentionally."
            ),
        })

    severity_rank = {"high": 0, "medium": 1, "info": 2}
    issues.sort(key=lambda i: severity_rank[i["severity"]])
    return {
        "target_jurisdiction": target,
        "own_markers_found": own_hits[:8],
        "governing_law_clauses": [re.sub(r"\s+", " ", g)[:160] for g in governing][:5],
        "status": "fail" if any(i["severity"] == "high" for i in issues)
                  else ("warn" if issues else "pass"),
        "issues": issues,
    }
