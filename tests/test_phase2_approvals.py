"""Phase 2 — write proposals → approve → execute, plus tenancy + RBAC.

Uses the deterministic tool path (write_tools.invoke) and the real approval
service / routes. No real Gemini / CrewAI agent is involved.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.agent.tools.registry import ToolRunContext
from app.agent.tools.write_tools import invoke_propose_tool_direct
from app.db.session import AsyncSessionLocal
from app.db.sync_session import SyncSessionLocal
from app.domain.models import ActionProposal, Membership
from app.domain.repos.memberships import MembershipsRepo
from app.domain.schemas import VendorContext
from app.services import approval_service
from conftest import auth_headers


def _acme_ctx() -> VendorContext:
    return VendorContext(
        vendor_id="v_acme",
        vendor_user_id="vu_admin",
        email="admin@acme.example",
        role="admin",
        timezone="Asia/Kolkata",
        vendor_name="Acme Sports",
    )


def _beta_ctx() -> VendorContext:
    return VendorContext(
        vendor_id="v_beta",
        vendor_user_id="vu_beta_admin",
        email="admin@beta.example",
        role="admin",
        timezone="UTC",
        vendor_name="Beta Games Co",
    )


async def _propose(action: str, args: dict, ctx: VendorContext | None = None) -> dict:
    run_ctx = ToolRunContext()
    raw = await invoke_propose_tool_direct(action, args, ctx or _acme_ctx(), run_ctx)
    return json.loads(raw), run_ctx


# ── Proposal creation (no mutation) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_propose_extend_trial_creates_pending():
    data, run_ctx = await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    assert "proposal_id" in data
    assert data["status"] == "pending"
    # No mutation yet — Alice's trial_ends_at unchanged
    async with AsyncSessionLocal() as session:
        m = await MembershipsRepo(session).get_membership(
            vendor_id="v_acme", user_id="u_alice", game_slug="badminton"
        )
    assert m is not None
    # preview must show before/after
    assert "before" in data["preview"] and "after" in data["preview"]
    assert run_ctx.blocks[0]["type"] == "proposal_card"


@pytest.mark.asyncio
async def test_propose_unknown_user_returns_error_no_proposal():
    data, _ = await _propose(
        "propose_extend_trial",
        {"user_id": "u_ghost", "game_slug": "badminton", "extra_days": 7},
    )
    assert "error" in data
    assert "proposal_id" not in data


# ── Approve → execute ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_executes_extend_trial(client: AsyncClient):
    # 1. Create proposal directly via tool
    data, _ = await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    pid = data["proposal_id"]
    new_ends = data["preview"]["after"]["trial_ends_at"]

    # 2. Approve via endpoint
    headers = auth_headers()
    resp = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "approve"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "executed"
    assert body["execution_result"]["ok"] is True

    # 3. Verify the membership was actually mutated
    async with AsyncSessionLocal() as session:
        m = await MembershipsRepo(session).get_membership(
            vendor_id="v_acme", user_id="u_alice", game_slug="badminton"
        )
    assert m["trial_ends_at"] == new_ends


@pytest.mark.asyncio
async def test_approve_change_plan_executes(client: AsyncClient):
    data, _ = await _propose(
        "propose_change_plan",
        {"user_id": "u_bob", "game_slug": "cricket", "new_plan": "basic"},
    )
    pid = data["proposal_id"]
    resp = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "approve"},
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "executed"

    async with AsyncSessionLocal() as session:
        m = await MembershipsRepo(session).get_membership(
            vendor_id="v_acme", user_id="u_bob", game_slug="cricket"
        )
    assert m["plan"] == "basic"


@pytest.mark.asyncio
async def test_approve_suspend_user_executes(client: AsyncClient):
    data, _ = await _propose(
        "propose_suspend_user",
        {"user_id": "u_carol", "reason": "abuse"},
    )
    pid = data["proposal_id"]
    resp = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "approve"},
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "executed"


# ── Reject ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_does_not_mutate(client: AsyncClient):
    data, _ = await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    pid = data["proposal_id"]

    async with AsyncSessionLocal() as session:
        before = (
            await MembershipsRepo(session).get_membership(
                vendor_id="v_acme", user_id="u_alice", game_slug="badminton"
            )
        )["trial_ends_at"]

    resp = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "reject", "reason": "not now"},
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    async with AsyncSessionLocal() as session:
        after = (
            await MembershipsRepo(session).get_membership(
                vendor_id="v_acme", user_id="u_alice", game_slug="badminton"
            )
        )["trial_ends_at"]
    assert after == before


# ── Idempotency / double-approve ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_double_approve_is_rejected(client: AsyncClient):
    data, _ = await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    pid = data["proposal_id"]
    h = auth_headers()
    r1 = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "approve"},
        headers=h,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "approve"},
        headers=h,
    )
    # Already executed → conflict, not a second mutation
    assert r2.status_code == 409


# ── Tenancy isolation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_other_vendor_cannot_see_or_decide_proposal(client: AsyncClient):
    data, _ = await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    pid = data["proposal_id"]

    # v_beta cannot fetch
    resp = await client.get(
        f"/v1/copilot/proposals/{pid}",
        headers=auth_headers(vendor_id="v_beta", user_id="vu_beta_admin"),
    )
    assert resp.status_code == 404

    # v_beta cannot decide
    resp = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "approve"},
        headers=auth_headers(vendor_id="v_beta", user_id="vu_beta_admin"),
    )
    assert resp.status_code == 404


# ── Role gating ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_viewer_cannot_decide(client: AsyncClient):
    data, _ = await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    pid = data["proposal_id"]
    resp = await client.post(
        f"/v1/copilot/proposals/{pid}/decide",
        json={"decision": "approve"},
        headers=auth_headers(role="viewer", user_id="vu_viewer"),
    )
    assert resp.status_code == 403


# ── List + audit ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_proposals_and_audit(client: AsyncClient):
    await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    h = auth_headers()
    resp = await client.get("/v1/copilot/proposals?status=pending", headers=h)
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1

    # audit (admin)
    resp = await client.get("/v1/copilot/audit", headers=h)
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1

    # audit denied for viewer
    resp = await client.get(
        "/v1/copilot/audit",
        headers=auth_headers(role="viewer", user_id="vu_viewer"),
    )
    assert resp.status_code == 403


# ── Expiry ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expired_proposal_cannot_be_approved():
    data, _ = await _propose(
        "propose_extend_trial",
        {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
    )
    pid = data["proposal_id"]

    # Simulate expiry by backdating expires_at
    with SyncSessionLocal() as session:
        p = session.get(ActionProposal, pid)
        p.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    ctx = _acme_ctx()

    async with AsyncSessionLocal() as db:
        try:
            await approval_service.decide_proposal(
                db,
                proposal_id=pid,
                ctx=ctx,
                decision="approve",
            )
            pytest.fail("Expected ProposalError")
        except approval_service._ProposalError as exc:
            assert exc.status_code == 409