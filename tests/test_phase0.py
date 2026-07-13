"""Phase 0 integration tests — foundation endpoints (agent mocked in Phase 1)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import auth_headers


# ── Health ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "HobbyFi Vendor Copilot API"
    assert body["database"] == "postgresql"
    assert body["gemini_configured"] is True
    assert body["version"] == "0.1.0"


# ── Auth / whoami ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_whoami_returns_context(client: AsyncClient):
    headers = auth_headers()
    resp = await client.get("/v1/copilot/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["vendor_id"] == "v_acme"
    assert body["vendor_user_id"] == "vu_admin"
    assert body["role"] == "admin"
    assert body["vendor_name"] == "Acme Sports"
    assert body["timezone"] == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_missing_auth_headers_401(client: AsyncClient):
    resp = await client.get("/v1/copilot/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_nonexistent_vendor_401(client: AsyncClient):
    headers = auth_headers(vendor_id="v_ghost")
    resp = await client.get("/v1/copilot/me", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_role_mismatch_400(client: AsyncClient):
    headers = auth_headers(role="owner")  # vu_admin is 'admin', not 'owner'
    resp = await client.get("/v1/copilot/me", headers=headers)
    assert resp.status_code == 400


# ── Sessions ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_get_session(client: AsyncClient):
    headers = auth_headers()
    resp = await client.post("/v1/copilot/sessions", json={}, headers=headers)
    assert resp.status_code == 201
    session = resp.json()
    assert session["vendor_id"] == "v_acme"
    sid = session["id"]

    resp = await client.get(f"/v1/copilot/sessions/{sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == sid


@pytest.mark.asyncio
async def test_session_not_found_404(client: AsyncClient):
    headers = auth_headers()
    resp = await client.get("/v1/copilot/sessions/cs_doesnotexist", headers=headers)
    assert resp.status_code == 404


# ── Messages ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_and_list_messages(client: AsyncClient):
    headers = auth_headers()

    # Create session
    resp = await client.post("/v1/copilot/sessions", json={}, headers=headers)
    sid = resp.json()["id"]

    # Post two turns (each produces user + assistant)
    await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "What is today's revenue?"},
        headers=headers,
    )
    await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "List trial users of badminton"},
        headers=headers,
    )

    # List — 2 user + 2 assistant
    resp = await client.get(f"/v1/copilot/sessions/{sid}/messages", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == sid
    assert len(body["messages"]) == 4
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"]["text"] == "What is today's revenue?"
    assert body["messages"][1]["role"] == "assistant"
    assert "Mock answer" in body["messages"][1]["content"]["text"]
    assert body["messages"][2]["role"] == "user"
    assert body["messages"][2]["content"]["text"] == "List trial users of badminton"
    assert body["messages"][3]["role"] == "assistant"


@pytest.mark.asyncio
async def test_post_message_to_nonexistent_session_404(client: AsyncClient):
    headers = auth_headers()
    resp = await client.post(
        "/v1/copilot/sessions/cs_doesnotexist/messages",
        json={"content": "hello"},
        headers=headers,
    )
    assert resp.status_code == 404


# ── Tenancy isolation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_vendor_cannot_access_session(client: AsyncClient):
    # Create session as v_acme admin
    resp = await client.post(
        "/v1/copilot/sessions", json={}, headers=auth_headers()
    )
    sid = resp.json()["id"]

    # Try to access as v_beta admin
    resp = await client.get(
        f"/v1/copilot/sessions/{sid}",
        headers=auth_headers(vendor_id="v_beta", user_id="vu_beta_admin"),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_vendor_cannot_list_messages(client: AsyncClient):
    # Create session as v_acme
    resp = await client.post(
        "/v1/copilot/sessions", json={}, headers=auth_headers()
    )
    sid = resp.json()["id"]

    # Post a message
    await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "secret"},
        headers=auth_headers(),
    )

    # Try to list as v_beta
    resp = await client.get(
        f"/v1/copilot/sessions/{sid}/messages",
        headers=auth_headers(vendor_id="v_beta", user_id="vu_beta_admin"),
    )
    assert resp.status_code == 404


# ── Seed (dev-only admin) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_requires_admin_role(client: AsyncClient):
    resp = await client.post(
        "/v1/admin/seed",
        headers=auth_headers(role="viewer", user_id="vu_viewer"),
    )
    assert resp.status_code == 403
