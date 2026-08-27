"""Unit tests — citation parsing & validation (symbolic layer)."""

from __future__ import annotations

from app.services.verification.citation_validator import (
    extract_citations,
    normalize_case_name,
    validate_citations,
)


def test_us_case_citation_valid():
    text = "As held in Roe v. Wade, 410 U.S. 113 (1973), privacy extends further."
    report = validate_citations(text)
    assert report["total"] >= 1
    assert any(
        c["kind"] == "case" and c["status"] == "valid" for c in report["malformed"]
    ) is False
    assert report["valid"] >= 1


def test_us_statute_valid():
    text = "Under 42 U.S.C. § 1983, plaintiffs may sue."
    checks = extract_citations(text)
    assert any("1983" in c for c in checks)


def test_cfr_regulation_valid():
    assert any("1003" in c for c in extract_citations("See 8 C.F.R. § 1003.2 for details."))


def test_oscola_neutral_citation():
    text = "The court reasoned in [2020] EWCA Civ 1 that liability was unclear."
    report = validate_citations(text)
    assert report["valid"] >= 1


def test_uk_law_report_citation():
    text = "Donoghue v Stevenson [1932] AC 562 established the neighbour principle."
    report = validate_citations(text)
    styles = set(report["styles_detected"])
    assert styles & {"oscola", "bluebook"}


def test_malformed_case_missing_year():
    text = "In Smith v Jones, 123 F.3d 456 the court said otherwise."
    report = validate_citations(text)
    malformed = [m for m in report["malformed"] if "year" in m.get("reason", "")]
    assert len(malformed) >= 1


def test_no_citations_is_clean():
    report = validate_citations("This paragraph has no authorities at all.")
    assert report["total"] == 0
    assert report["status"] == "pass"


def test_normalize_case_name():
    assert normalize_case_name("ROE   v.  WADE") == "ROE v. WADE"
    assert normalize_case_name("Roe v. Wade") == "Roe v. Wade"


def test_extract_deduplicates():
    text = "Brown v. Board of Education, 347 U.S. 483 (1954) and again Brown v. Board of Education, 347 U.S. 483 (1954)."
    found = extract_citations(text)
    matches = [c for c in found if "347" in c]
    assert len(matches) == 1
