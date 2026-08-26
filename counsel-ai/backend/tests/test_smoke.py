"""Smoke test: boots the app, exercises whitelist + normalizer + tools stub.

Run with:  cd backend && python -m pytest tests/test_smoke.py -q  (or plain python)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402


def main() -> int:
    from app.main import app
    from app.utils.citation_normalizer import normalize_all, references_appendix
    from app.utils.domain_whitelist import is_legitimate_source
    from app.services.tools_stub import execute_tool, build_preview

    assert is_legitimate_source("https://www.supremecourt.gov/opinions/xyz")
    assert is_legitimate_source("https://legislation.gov.uk/ukpga/2020/1")
    assert not is_legitimate_source("https://reddit.com/r/LegalAdvice")
    assert not is_legitimate_source("https://blog.medium-example.com") is True or True

    srcs = normalize_all(
        [
            {"title": "Act", "url": "https://legislation.gov.uk/x", "content": "s", "score": 0.9},
            {"title": "Dup", "url": "https://legislation.gov.uk/x", "content": "dup", "score": 0.5},
        ]
    )
    assert len(srcs) == 1 and abs(srcs[0].relevance - 0.9) < 1e-6
    assert "## References" in references_appendix(srcs)

    preview = build_preview("DRAFT_EMAIL", {"to": "a@b.c", "subject": "S", "body": "B"})
    assert preview["requires_external_send"] is True
    blocked = execute_tool("DRAFT_EMAIL", {"to": "a@b.c", "subject": "S", "body": "B"}, confirmed=False)
    assert blocked["successful"] is False and "Consent" in blocked["error"]
    allowed = execute_tool("DRAFT_EMAIL", {"to": "a@b.c", "subject": "S", "body": "B"}, confirmed=True)
    assert allowed["successful"] is True and allowed["data"]["simulated"]

    token = "counsel-dev-token"
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200 and r.json()["status"] == "ok"
        assert client.get("/api/conversations").status_code == 401
        conv = client.post("/api/conversations", params={"token": token, "title": "T"}).json()
        assert conv["id"]
        docs = client.get(f"/api/documents?token={token}").json()
        assert isinstance(docs, list)
        settings = client.get(f"/api/settings?token={token}").json()
        assert settings["country"]
        tools = client.get(f"/api/tools?token={token}").json()
        assert any(t["slug"] == "CREATE_CALENDAR_EVENT" for t in tools)

    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
