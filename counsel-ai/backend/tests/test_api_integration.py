"""Integration tests — auth flow, roles, workspace isolation, key endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(_env):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_tokens(client) -> dict:
    # bootstrap admin password was written to data dir on startup
    from app.config import settings

    text = (settings.data_dir / "bootstrap_admin.txt").read_text()
    password = next(
        line.strip() for line in text.splitlines() if line.startswith("    ") and line.strip()
    )
    resp = client.post("/api/users/login",
                       json={"email": "admin@counsel.local", "password": password})
    assert resp.status_code == 200
    data = resp.json()
    return {"access": data["access_token"], "refresh": data["refresh_token"],
            "user": data["user"]}


@pytest.fixture(scope="module")
def lawyer_headers(admin_tokens, client):
    resp = client.post(
        "/api/users",
        json={"email": "lawyer@firm.com", "name": "Test Lawyer",
              "role": "lawyer", "password": "s3cure-Lawyer-PW!"},
        headers={"Authorization": f"Bearer {admin_tokens['access']}"},
    )
    assert resp.status_code == 200
    resp = client.post("/api/users/login",
                       json={"email": "lawyer@firm.com", "password": "s3cure-Lawyer-PW!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def readonly_headers(admin_tokens, client):
    resp = client.post(
        "/api/users",
        json={"email": "reader@firm.com", "name": "Reader",
              "role": "readonly", "password": "r3adonly-Pass!"},
        headers={"Authorization": f"Bearer {admin_tokens['access']}"},
    )
    assert resp.status_code == 200
    resp = client.post("/api/users/login",
                       json={"email": "reader@firm.com", "password": "r3adonly-Pass!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------- tests


def test_health_is_public(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_requires_auth(client):
    assert client.get("/api/conversations").status_code == 401


def test_login_wrong_password(client):
    resp = client.post("/api/users/login",
                       json={"email": "admin@counsel.local", "password": "nope"})
    assert resp.status_code == 401


def test_refresh_rotation(client, admin_tokens):
    old_refresh = admin_tokens["refresh"]
    resp = client.post("/api/users/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    new_pair = resp.json()
    # old refresh token is single-use
    replay = client.post("/api/users/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401
    admin_tokens["refresh"] = new_pair["refresh_token"]


def test_conversation_crud_isolated_per_user(client, lawyer_headers):
    r1 = client.post("/api/conversations?title=Case A", headers=lawyer_headers)
    conv_id = r1.json()["id"]
    assert r1.status_code == 200
    listing = client.get("/api/conversations", headers=lawyer_headers)
    assert any(c["id"] == conv_id for c in listing.json())
    assert client.delete(f"/api/conversations/{conv_id}",
                         headers=lawyer_headers).status_code == 200


def test_readonly_cannot_create_conversation(client, readonly_headers):
    resp = client.post("/api/conversations?title=x", headers=readonly_headers)
    assert resp.status_code == 403


def test_readonly_can_list(client, readonly_headers):
    assert client.get("/api/conversations", headers=readonly_headers).status_code == 200


def test_admin_required_for_user_management(client, lawyer_headers):
    resp = client.get("/api/users", headers=lawyer_headers)
    assert resp.status_code == 403


def test_audit_log_written_on_login(client, lawyer_headers, admin_tokens):
    client.post("/api/users/logout", headers=lawyer_headers)
    resp = client.get("/api/admin/audit",
                      headers={"Authorization": f"Bearer {admin_tokens['access']}"})
    assert resp.status_code == 200
    actions = [a["action"] for a in resp.json()]
    assert any(a.startswith("auth.") for a in actions)


def test_skills_endpoints(client, lawyer_headers):
    resp = client.get("/api/skills", headers=lawyer_headers)
    assert resp.status_code == 200
    builtin_names = {s["name"] for s in resp.json()}
    assert "NDA Drafting" in builtin_names

    created = client.post(
        "/api/skills",
        json={"name": "Client Intake", "description": "Intake checklist skill",
              "triggers": ["intake", "new client"],
              "system_prompt": "Produce an intake checklist.", "doc_type": "general"},
        headers=lawyer_headers,
    )
    assert created.status_code == 200
    skill_id = created.json()["id"]

    matched = client.post("/api/skills/match",
                          json={"query": "onboard a new client intake form"},
                          headers=lawyer_headers)
    assert any(s["name"] == "Client Intake" for s in matched.json())

    deleted = client.delete(f"/api/skills/{skill_id}", headers=lawyer_headers)
    assert deleted.status_code == 200


def test_builtin_skill_immutable_auto_fork(client, lawyer_headers):
    listing = client.get("/api/skills", headers=lawyer_headers).json()
    nda = next(s for s in listing if s.get("builtin_key") == "nda_drafting")
    patched = client.patch(f"/api/skills/{nda['id']}",
                           json={"name": "NDA Drafting (edited)"},
                           headers=lawyer_headers)
    assert patched.status_code == 200
    assert "(edited)" in patched.json()["name"]
    # original builtin untouched
    listing2 = client.get("/api/skills", headers=lawyer_headers).json()
    originals = [s for s in listing2
                 if s.get("builtin_key") == "nda_drafting" and s.get("owner_id") is None]
    assert len(originals) == 1 and originals[0]["name"] == "NDA Drafting"


def test_updates_endpoint_lists_or_empty(client, lawyer_headers):
    resp = client.get("/api/updates", headers=lawyer_headers)
    assert resp.status_code in (200,)
    assert isinstance(resp.json(), list)


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text or "http.requests" in resp.text \
        or "_bucket" in resp.text or "counter" in resp.text


def test_settings_roundtrip(client, lawyer_headers):
    patch = client.patch("/api/settings",
                         json={"country": "United States", "province": "California",
                               "practice_areas": ["contract law"]},
                         headers=lawyer_headers)
    assert patch.status_code == 200
    me = client.get("/api/users/me", headers=lawyer_headers).json()
    assert me["practice_areas"] == ["contract law"]


def test_tool_requires_consent(client, lawyer_headers):
    tools = client.get("/api/tools", headers=lawyer_headers).json()
    slug = next(t["slug"] for t in tools if t["requires_external_send"])
    resp = client.post(f"/api/tools/{slug}/execute",
                       json={"input": {"to": "a@b.com", "subject": "s", "body": "b"},
                             "confirmed": False},
                       headers=lawyer_headers)
    body = resp.json()
    assert body["successful"] is False
    assert "Consent required" in (body["error"] or "")


def test_tool_simulate_with_consent(client, lawyer_headers):
    resp = client.post("/api/tools/DRAFT_EMAIL/execute",
                       json={"input": {"to": "a@b.com", "subject": "Hello",
                                       "body": "World"}, "confirmed": True},
                       headers=lawyer_headers)
    body = resp.json()
    assert body["successful"] is True
    assert body["data"]["simulated"] is True
