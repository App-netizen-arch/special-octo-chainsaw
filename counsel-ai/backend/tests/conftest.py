"""Shared pytest fixtures — isolated temp data dir + fresh DB per session.

IMPORTANT: environment must be configured at *module import time* because
pytest collects (and therefore imports) every test module before any fixture
runs; ``app.config`` reads its data-dir/env on first import.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="counsel-tests-")
os.environ.setdefault("COUNSEL_DATA_DIR", _TMP)
os.environ["COUNSEL_JWT_SECRET"] = "test-secret-test-secret-test-secret"
os.environ["COUNSEL_ENCRYPT_AT_REST"] = "true"
os.environ["UPDATES_ENABLED"] = "false"
os.environ.pop("LOCAL_MODEL_PATH", None)

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _env():
    """Ensure schema exists once for the whole session."""
    from app.database import init_db

    init_db()
    yield


@pytest.fixture()
def sample_document() -> str:
    return (
        "# MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
        'This Non-Disclosure Agreement ("Agreement") is entered into as of 2026-01-01, '
        'between Party A ("Disclosing Party") and Party B ("Receiving Party").\n\n'
        "## 1. Purpose\n\nThe Parties wish to explore a business relationship.\n\n"
        "## 2. Confidential Information\n\nConfidential Information means any non-public "
        "information disclosed by either Party.\n\n"
        "## 3. Obligations of the Receiving Party\n\nThe Receiving Party shall use the "
        "Confidential Information solely for the Purpose.\n\n"
        "## 4. Exclusions\n\nInformation that is or becomes public through no fault of "
        "the Receiving Party is excluded.\n\n"
        "## 5. Term and Termination\n\nThis Agreement continues for 2 years.\n\n"
        "## 6. Governing Law\n\nThis Agreement is governed by the laws of California.\n\n"
        "## Signatures\n\n| | Party A | Party B |\n|---|---|---|\n| Signature | ____ | ____ |\n\n"
        "---\n*Drafted with Counsel AI. This tool assists drafting and research; it is not "
        "a substitute for professional legal judgment.*\n"
    )
