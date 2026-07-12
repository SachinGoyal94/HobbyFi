"""Phase 1 — read tools and vendor scoping (no LLM required)."""

from __future__ import annotations

import json

import pytest

from app.agent.tools.read_tools import invoke_read_tool_direct
from app.agent.tools.registry import ToolRunContext
from app.db.session import AsyncSessionLocal
from app.db.sync_session import SyncSessionLocal
from app.domain.repos.games import GamesRepo
from app.domain.repos.memberships import MembershipsRepo
from app.domain.repos.revenue import RevenueRepo
from app.domain.repos.users import UsersRepo
from app.domain.schemas import VendorContext


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


async def _tool(name: str, args: dict | None = None, ctx: VendorContext | None = None):
    run_ctx = ToolRunContext()
    raw = await invoke_read_tool_direct(name, args or {}, ctx or _acme_ctx(), run_ctx)
    return json.loads(raw), run_ctx


# ── Repo-level scoping ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_games_repo_scoped_to_vendor():
    async with AsyncSessionLocal() as session:
        acme = await GamesRepo(session).list_games(vendor_id="v_acme")
        beta = await GamesRepo(session).list_games(vendor_id="v_beta")
    acme_slugs = {g["slug"] for g in acme}
    beta_slugs = {g["slug"] for g in beta}
    assert acme_slugs == {"badminton", "cricket"}
    assert beta_slugs == {"tennis"}
    assert "tennis" not in acme_slugs
    assert "badminton" not in beta_slugs


@pytest.mark.asyncio
async def test_trial_users_badminton_only_acme():
    async with AsyncSessionLocal() as session:
        rows = await MembershipsRepo(session).list_trials(
            vendor_id="v_acme", game_slug="badminton"
        )
    user_ids = {r["user_id"] for r in rows}
    assert "u_alice" in user_ids
    assert "u_carol" in user_ids
    assert "u_beta_eve" not in user_ids  # other vendor
    assert "u_bob" not in user_ids  # pro cricket, not trial


@pytest.mark.asyncio
async def test_revenue_today_all_games_acme():
    async with AsyncSessionLocal() as session:
        rev = await RevenueRepo(session).get_revenue(
            vendor_id="v_acme", timezone_name="Asia/Kolkata"
        )
    assert rev["found"] is True
    assert rev["net_cents"] == 128_500
    assert rev["net"] == "1285.00"


@pytest.mark.asyncio
async def test_revenue_cross_vendor_isolation():
    async with AsyncSessionLocal() as session:
        acme = await RevenueRepo(session).get_revenue(vendor_id="v_acme")
        beta = await RevenueRepo(session).get_revenue(vendor_id="v_beta")
    assert acme["net_cents"] == 128_500
    assert beta["net_cents"] == 9_900


@pytest.mark.asyncio
async def test_search_users_does_not_leak_other_vendor():
    async with AsyncSessionLocal() as session:
        hits = await UsersRepo(session).search(vendor_id="v_acme", query="eve")
    assert hits == []
    async with AsyncSessionLocal() as session:
        hits = await UsersRepo(session).search(vendor_id="v_beta", query="eve")
    assert len(hits) == 1
    assert hits[0]["id"] == "u_beta_eve"


@pytest.mark.asyncio
async def test_get_user_other_vendor_returns_none():
    async with AsyncSessionLocal() as session:
        user = await UsersRepo(session).get_user(vendor_id="v_acme", user_id="u_beta_eve")
    assert user is None


# ── Tool wrappers ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_list_trial_users_badminton():
    data, run_ctx = await _tool("list_trial_users", {"game_slug": "badminton", "limit": 20})
    assert data["count"] == 2
    ids = {u["user_id"] for u in data["trial_users"]}
    assert ids == {"u_alice", "u_carol"}
    assert run_ctx.traces[0]["tool"] == "list_trial_users"
    assert any(b["type"] == "table" for b in run_ctx.blocks)


@pytest.mark.asyncio
async def test_tool_get_revenue():
    data, run_ctx = await _tool("get_revenue", {})
    assert data["found"] is True
    assert data["net_cents"] == 128_500
    assert run_ctx.blocks and run_ctx.blocks[0]["type"] == "kpi"


@pytest.mark.asyncio
async def test_tool_list_games():
    data, _ = await _tool("list_games", {})
    slugs = {g["slug"] for g in data["games"]}
    assert slugs == {"badminton", "cricket"}


@pytest.mark.asyncio
async def test_tool_search_users_alice():
    data, _ = await _tool("search_users", {"query": "alice"})
    assert data["count"] == 1
    assert data["users"][0]["id"] == "u_alice"


@pytest.mark.asyncio
async def test_tool_get_user_with_memberships():
    data, _ = await _tool("get_user", {"user_id": "u_alice"})
    assert data["found"] is True
    assert data["user"]["display_name"] == "Alice"
    memberships = data["user"]["memberships"]
    assert any(m["game_slug"] == "badminton" for m in memberships)


@pytest.mark.asyncio
async def test_tool_get_membership():
    data, _ = await _tool("get_membership", {"user_id": "u_alice", "game_slug": "badminton"})
    assert data["found"] is True
    assert data["membership"]["plan"] == "trial"


@pytest.mark.asyncio
async def test_tool_vendor_summary():
    data, run_ctx = await _tool("get_vendor_summary", {})
    assert data["game_count"] == 2
    assert data["active_users"] >= 3
    assert data["active_trials"] >= 2
    assert run_ctx.blocks[0]["type"] == "kpi"


@pytest.mark.asyncio
async def test_tool_beta_cannot_see_acme_trials():
    data, _ = await _tool("list_trial_users", {"game_slug": "badminton"}, ctx=_beta_ctx())
    # Beta has no badminton game / trials
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_tool_beta_sees_own_revenue_only():
    data, _ = await _tool("get_revenue", {}, ctx=_beta_ctx())
    assert data["found"] is True
    assert data["net_cents"] == 9_900
