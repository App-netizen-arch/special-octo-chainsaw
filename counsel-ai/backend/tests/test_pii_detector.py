"""Unit tests — PII detection & redaction."""

from __future__ import annotations

from app.utils.pii import detect, redact_text


def test_email_detection():
    findings = detect("Contact jane.doe@firm.com about the case.", include_names=False)
    kinds = {f.kind for f in findings}
    assert "email" in kinds


def test_phone_detection():
    findings = detect("Call (415) 555-2671 today.", include_names=False)
    assert any(f.kind == "phone" for f in findings)


def test_ssn_detection():
    findings = detect("SSN on file: 123-45-6789.", include_names=False)
    assert any(f.kind == "ssn" for f in findings)


def test_year_not_flagged_as_phone():
    findings = detect("The contract was signed in 2019 and amended in 2020.", include_names=False)
    assert not any(f.kind == "phone" for f in findings)


def test_redaction_removes_email_and_phone():
    text = "Email jane@lawfirm.com or call 415-555-2671."
    redacted = redact_text(text)
    assert "jane@lawfirm.com" not in redacted
    assert "415-555-2671" not in redacted
    assert "[REDACTED-EMAIL]" in redacted
    assert "[REDACTED-PHONE]" in redacted


def test_name_hint_detection():
    findings = detect("Mr John Smith attended the deposition.", include_names=True)
    assert any(f.kind == "person_name" for f in findings)
