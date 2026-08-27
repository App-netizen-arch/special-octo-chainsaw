"""Unit tests — clause structure rules & jurisdiction checker."""

from __future__ import annotations

from app.services.verification.clause_rules import check_clauses, detect_doc_type
from app.services.verification.jurisdiction_checker import check_jurisdiction


def _nda_text() -> str:
    return (
        "# MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
        "## 1. Purpose\n\nExplore a relationship.\n\n"
        "## 2. Confidential Information\n\nMeans non-public information.\n\n"
        "## 3. Obligations of the Receiving Party\n\nUse solely for the Purpose.\n\n"
        "## 4. Exclusions\n\nPublic information excluded.\n\n"
        "## 5. Term and Termination\n\nTwo years.\n\n"
        "## 6. Governing Law\n\nLaws of California.\n\n"
        "## Signatures\n\n| Signature | ____ |\n\n"
        "*This draft is not legal advice.*\n"
    )


def test_detect_nda_type():
    assert detect_doc_type(_nda_text()) == "nda"


def test_complete_nda_passes(sample_document):
    report = check_clauses(sample_document, doc_type="nda")
    assert report["status"] in ("pass", "warn")
    blocking = [i for i in report["issues"] if i["severity"] == "high"]
    assert blocking == []


def test_nda_missing_term_section_fails():
    text = _nda_text().replace("## 5. Term and Termination\n\nTwo years.\n\n", "")
    report = check_clauses(text, doc_type="nda")
    codes = [i["code"] for i in report["issues"]]
    assert "missing_section" in codes
    missing = [i["section"] for i in report["issues"] if i["code"] == "missing_section"]
    assert any("Term" in s for s in missing)
    assert report["status"] == "fail"


def test_placeholders_flagged():
    report = check_clauses(_nda_text(), doc_type="nda")
    placeholder_issues = [i for i in report["issues"] if i["code"] == "placeholders_present"]
    assert len(placeholder_issues) == 1  # signature underscores are intentional but flagged as info


def test_disclaimer_required():
    text = _nda_text().replace("*This draft is not legal advice.*", "")
    report = check_clauses(text, doc_type="nda")
    codes = [i["code"] for i in report["issues"]]
    assert "missing_disclaimer" in codes


# ------------------------------------------------------------------ jurisdiction


def test_jurisdiction_present(sample_document):
    report = check_jurisdiction(sample_document, province="California", country="United States")
    assert report["status"] in ("pass", "warn")


def test_jurisdiction_absent_warns():
    text = "# CONTRACT\n\n## Governing Law\n\nThis is governed by neutral law.\n"
    report = check_jurisdiction(text, province="New York", country="United States")
    codes = [i["code"] for i in report["issues"]]
    assert "jurisdiction_not_referenced" in codes


def test_conflicting_jurisdiction_flagged():
    text = (
        "# AGREEMENT\n\nThis Agreement is governed by New York law. "
        "Pursuant to the New York Civil Practice Law and Rules, venue lies in New York County. "
        "The parties submit to the jurisdiction of the New York courts.\n\n"
        "*Draft disclaimer: not legal advice.*\n"
    )
    report = check_jurisdiction(text, province="California", country="United States")
    codes = [i["code"] for i in report["issues"]]
    assert "conflicting_jurisdiction" in codes
