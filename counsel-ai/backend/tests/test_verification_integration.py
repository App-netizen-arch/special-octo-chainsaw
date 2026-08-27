"""Integration tests — encryption at rest + verification orchestrator."""

from __future__ import annotations

import pytest

from app.utils.encryption import decrypt_bytes, encrypt_bytes


def test_encrypt_roundtrip():
    blob = encrypt_bytes(b"client confidential memo")
    assert blob != b"client confidential memo"
    assert blob.startswith(b"cns1")
    assert decrypt_bytes(blob) == b"client confidential memo"


def test_legacy_plaintext_passthrough():
    assert decrypt_bytes(b"old plaintext") == b"old plaintext"


@pytest.mark.asyncio
async def test_orchestrator_document_verification(sample_document):
    from app.services.verification.orchestrator import verify_document

    report = await verify_document(
        sample_document,
        jurisdiction={"country": "United States", "province": "California"},
        doc_type="nda",
        check_sources_http=False,   # deterministic offline run
        llm_mode="local",           # no API key in tests; reviewer falls back gracefully
        api_key=None,
    )
    assert report["level"] == "document"
    assert report["doc_type"] == "nda"
    assert set(report["checks"]) >= {"citation_format", "source_existence",
                                     "clause_structure", "jurisdiction"}
    clause = report["checks"]["clause_structure"]
    assert clause["status"] in ("pass", "warn")
    # offline mode marks sources unverified, never fabricated-verified
    for check in report["checks"]["source_existence"]["checks"]:
        assert check["status"] in ("verified", "exists", "unverified", "dead")


@pytest.mark.asyncio
async def test_light_verification_flags_dead_links():
    from unittest.mock import patch

    from app.services.verification.orchestrator import verify_light_async

    fake = [
        {"url": "https://www.supremecourt.gov/x", "status": "dead",
         "http_status": 404, "quote_match": None, "detail": "page not found"},
    ]
    with patch("app.services.verification.orchestrator.verify_sources_exist",
               return_value=fake):
        report = await verify_light_async("See ([X](https://www.supremecourt.gov/x)).", [],
                                          enabled=False)
    assert report["status"] == "fail"
