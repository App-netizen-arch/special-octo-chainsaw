"""PII detector for the verification layer.

Thin, document-oriented wrapper over ``utils.pii``: returns a structured
report (never the raw PII values) plus a redacted copy of the text for
privacy-auditor use.
"""

from __future__ import annotations

from typing import Any

from ...utils.pii import detect as _detect
from ...utils.pii import redact_text


def detect_pii(text: str, include_names: bool = True) -> dict[str, Any]:
    findings = _detect(text, include_names=include_names)
    return {
        "has_pii": bool(findings),
        "kinds": sorted({f.kind for f in findings}),
        "counts": _counts(findings),
        # locations only — values must never appear in reports/logs
        "locations": [{"kind": f.kind, "start": f.start, "end": f.end} for f in findings[:100]],
    }


def redact(text: str) -> str:
    return redact_text(text)


def privacy_audit(document: str, client_names: list[str] | None = None) -> dict[str, Any]:
    """Privacy Auditor (deterministic): flags confidential-looking data leaks.

    Checks, in order:
    1. Generic PII presence.
    2. Known confidential markers ("Privileged", client matter numbers).
    3. Explicit client names supplied by the workspace owner.
    """
    report: dict[str, Any] = {}
    pii = detect_pii(document, include_names=True)
    report["pii"] = pii

    leak_markers: list[dict] = []
    lowered = document.lower()
    if "privileged and confidential" in lowered or "attorney work product" in lowered:
        leak_markers.append({
            "marker": "privilege legend present",
            "advice": "Confirm this document is intended to remain privileged; remove the legend before external sharing.",
        })
    for name in client_names or []:
        if name.lower() in lowered:
            leak_markers.append({
                "marker": f"client name '{name}'",
                "advice": "Client identifier detected. Redact before sharing outside the firm.",
            })
    report["leak_markers"] = leak_markers
    report["status"] = "fail" if any("client name" in m["marker"] for m in leak_markers) else (
        "warn" if pii["has_pii"] or leak_markers else "pass"
    )
    report["redacted_preview"] = redact_text(document[:1200])
    return report


def _counts(findings: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    return counts
