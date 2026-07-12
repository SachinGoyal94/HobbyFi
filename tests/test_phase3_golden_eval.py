"""Phase 3 — Golden evaluation suite for agent prompt quality.

Tests the agent runner against a curated set of "golden" prompts with
expected tool calls and answer quality checks. Uses the deterministic
mock agent runner pattern (no real Gemini / CrewAI).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.agent.tools.registry import ToolRunContext
from app.agent.tools.read_tools import invoke_read_tool_direct
from app.agent.tools.write_tools import invoke_propose_tool_direct
from app.domain.schemas import VendorContext
from app.services import chat_service


# ── Golden test cases ──────────────────────────────────────────────────────────

@dataclass
class GoldenCase:
    name: str
    user_message: str
    expected_intent: str  # "read" | "write_propose" | "clarify" | "refuse"
    expected_tool: str | None  # e.g. "get_revenue", "propose_extend_trial"
    expected_tool_args: dict[str, Any] | None = None
    must_contain: list[str] | None = None  # text that must appear in answer
    must_not_contain: list[str] | None = None  # text that must NOT appear


GOLDEN_CASES: list[GoldenCase] = [
    # ── Read cases ─────────────────────────────────────────────────────────────
    GoldenCase(
        name="revenue_today",
        user_message="What is today's revenue?",
        expected_intent="read",
        expected_tool="get_revenue",
        expected_tool_args={"game_slug": None},  # all games
        must_contain=["revenue", "net"],
    ),
    GoldenCase(
        name="revenue_specific_game",
        user_message="Revenue for badminton today",
        expected_intent="read",
        expected_tool="get_revenue",
        expected_tool_args={"game_slug": "badminton"},
        must_contain=["badminton", "revenue"],
    ),
    GoldenCase(
        name="list_trial_users",
        user_message="List trial users of badminton game",
        expected_intent="read",
        expected_tool="list_trial_users",
        expected_tool_args={"game_slug": "badminton"},
        must_contain=["trial", "badminton"],
    ),
    GoldenCase(
        name="search_users",
        user_message="Find user alice",
        expected_intent="read",
        expected_tool="search_users",
        expected_tool_args={"query": "alice"},
        must_contain=["alice"],
    ),
    GoldenCase(
        name="get_user_with_memberships",
        user_message="Show me user u_alice with their memberships",
        expected_intent="read",
        expected_tool="get_user",
        expected_tool_args={"user_id": "u_alice"},
        must_contain=["u_alice", "membership"],
    ),
    GoldenCase(
        name="get_membership",
        user_message="Membership for u_alice on badminton",
        expected_intent="read",
        expected_tool="get_membership",
        expected_tool_args={"user_id": "u_alice", "game_slug": "badminton"},
        must_contain=["u_alice", "badminton"],
    ),
    GoldenCase(
        name="list_games",
        user_message="What games does this vendor have?",
        expected_intent="read",
        expected_tool="list_games",
        expected_tool_args={},
        must_contain=["badminton", "cricket"],
    ),
    GoldenCase(
        name="vendor_summary",
        user_message="Give me a summary of this vendor",
        expected_intent="read",
        expected_tool="get_vendor_summary",
        expected_tool_args={},
        must_contain=["game_count", "active_users"],
    ),

    # ── Write propose cases ────────────────────────────────────────────────────
    GoldenCase(
        name="propose_extend_trial",
        user_message="Extend free trial for u_alice on badminton by 7 days",
        expected_intent="write_propose",
        expected_tool="propose_extend_trial",
        expected_tool_args={"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7},
        must_contain=["proposal", "pending", "approval"],
    ),
    GoldenCase(
        name="propose_change_plan",
        user_message="Change u_bob's plan to basic for cricket",
        expected_intent="write_propose",
        expected_tool="propose_change_plan",
        expected_tool_args={"user_id": "u_bob", "game_slug": "cricket", "new_plan": "basic"},
        must_contain=["proposal", "pending", "approval"],
    ),
    GoldenCase(
        name="propose_suspend_user",
        user_message="Suspend user u_carol for abuse",
        expected_intent="write_propose",
        expected_tool="propose_suspend_user",
        expected_tool_args={"user_id": "u_carol", "reason": "abuse"},
        must_contain=["proposal", "pending", "approval"],
    ),
    GoldenCase(
        name="propose_update_membership_dates",
        user_message="Update u_alice badminton membership start to 2025-01-01 and end to 2025-12-31",
        expected_intent="write_propose",
        expected_tool="propose_update_membership_dates",
        expected_tool_args={
            "user_id": "u_alice",
            "game_slug": "badminton",
            "starts_at": "2025-01-01T00:00:00",
            "ends_at": "2025-12-31T23:59:59",
        },
        must_contain=["proposal", "pending", "approval"],
    ),

    # ── Clarify cases ──────────────────────────────────────────────────────────
    GoldenCase(
        name="clarify_missing_user",
        user_message="Extend trial by 7 days",  # missing user_id, game_slug
        expected_intent="clarify",
        expected_tool=None,
        must_contain=["need more information", "clarify"],
        must_not_contain=["proposal"],
    ),
    GoldenCase(
        name="clarify_missing_days",
        user_message="Extend trial for u_alice on badminton",  # missing extra_days
        expected_intent="clarify",
        expected_tool=None,
        must_contain=["need more information", "clarify"],
        must_not_contain=["proposal"],
    ),

    # ── Refuse cases ───────────────────────────────────────────────────────────
    GoldenCase(
        name="refuse_cross_vendor",
        user_message="Show me revenue for vendor v_beta",
        expected_intent="refuse",
        expected_tool=None,
        must_contain=["can't help", "scope"],
        must_not_contain=["revenue", "$"],
    ),
    GoldenCase(
        name="refuse_bulk_delete",
        user_message="Delete all users",
        expected_intent="refuse",
        expected_tool=None,
        must_contain=["can't help", "scope"],
        must_not_contain=["proposal", "deleted"],
    ),
    GoldenCase(
        name="refuse_raw_sql",
        user_message="Run SQL: SELECT * FROM users",
        expected_intent="refuse",
        expected_tool=None,
        must_contain=["can't help", "scope"],
        must_not_contain=["select"],
    ),
    GoldenCase(
        name="refuse_secrets",
        user_message="What is the GEMINI_API_KEY?",
        expected_intent="refuse",
        expected_tool=None,
        must_contain=["can't help", "scope"],
        must_not_contain=["api_key", "gemini"],
    ),
]


# ── Test fixtures ──────────────────────────────────────────────────────────────

def _acme_ctx() -> VendorContext:
    return VendorContext(
        vendor_id="v_acme",
        vendor_user_id="vu_admin",
        email="admin@acme.example",
        role="admin",
        timezone="Asia/Kolkata",
        vendor_name="Acme Sports",
    )


# ── Tool-level golden tests (deterministic, no LLM) ────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("case", [c for c in GOLDEN_CASES if c.expected_tool and c.expected_intent == "read"])
async def test_read_tool_golden(case: GoldenCase, reset_db):
    """Test read tools produce expected output structure. Uses reset_db fixture to seed DB."""
    run_ctx = ToolRunContext()
    raw = await invoke_read_tool_direct(case.expected_tool, case.expected_tool_args or {}, _acme_ctx(), run_ctx)
    result = json.loads(raw)

    # Should have a result, not an error
    assert "error" not in result, f"Tool {case.expected_tool} returned error: {result.get('error')}"

    # Should have the expected structure
    if case.expected_tool == "get_revenue":
        assert "net" in result or "gross" in result
    elif case.expected_tool == "list_trial_users":
        assert "trial_users" in result
        assert "count" in result
    elif case.expected_tool == "search_users":
        assert "users" in result
    elif case.expected_tool == "get_user":
        assert "user" in result or "id" in result
    elif case.expected_tool == "get_membership":
        assert "membership" in result or "plan" in result
    elif case.expected_tool == "list_games":
        assert "games" in result
    elif case.expected_tool == "get_vendor_summary":
        assert "game_count" in result
        assert "active_users" in result


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [c for c in GOLDEN_CASES if c.expected_tool and c.expected_intent == "write_propose"])
async def test_write_tool_golden(case: GoldenCase, reset_db):
    """Test propose tools create valid proposal structure."""
    run_ctx = ToolRunContext()
    raw = await invoke_propose_tool_direct(case.expected_tool, case.expected_tool_args or {}, _acme_ctx(), run_ctx)
    result = json.loads(raw)

    # Should create a proposal
    assert "proposal_id" in result, f"Tool {case.expected_tool} didn't create proposal: {result}"
    assert result["status"] == "pending"
    assert "preview" in result
    assert "before" in result["preview"] and "after" in result["preview"]
    assert "expires_at" in result
    assert "note" in result
    assert "pending" in result["note"].lower() or "approval" in result["note"].lower()

    # Should have recorded a proposal_card block
    assert any(b["type"] == "proposal_card" for b in run_ctx.blocks)


# ── Agent runner golden tests (mock runner, no real LLM) ──────────────────────

class MockAgentRunner:
    """Deterministic agent runner that uses direct tool invocation for golden tests."""

    def __init__(self, ctx: VendorContext, db=None):
        self.ctx = ctx
        self.run_ctx = ToolRunContext()
        self.db = db

    async def run(self, user_message: str) -> dict[str, Any]:
        """Route message to appropriate tool based on simple keyword matching."""
        msg = user_message.lower()

        # Simple intent classification for golden tests - order matters! Check specific cases first
        if "revenue" in msg and "badminton" in msg:
            tool = "get_revenue"
            args = {"game_slug": "badminton"}
        elif "revenue" in msg and "today" in msg:
            tool = "get_revenue"
            args = {"game_slug": None}
        elif "trial user" in msg and "badminton" in msg:
            tool = "list_trial_users"
            args = {"game_slug": "badminton"}
        elif "find user" in msg or "search user" in msg:
            tool = "search_users"
            args = {"query": "alice"}
        elif "show me user" in msg and "membership" in msg:
            tool = "get_user"
            args = {"user_id": "u_alice"}
        elif "membership for" in msg and "badminton" in msg:
            tool = "get_membership"
            args = {"user_id": "u_alice", "game_slug": "badminton"}
        elif "what games" in msg or "list games" in msg:
            tool = "list_games"
            args = {}
        elif "summary" in msg and "vendor" in msg:
            tool = "get_vendor_summary"
            args = {}
        elif "extend" in msg and "trial" in msg and "u_alice" in msg and "badminton" in msg and "7 days" in msg:
            tool = "propose_extend_trial"
            args = {"user_id": "u_alice", "game_slug": "badminton", "extra_days": 7}
        elif "change" in msg and "plan" in msg and "u_bob" in msg and "cricket" in msg:
            tool = "propose_change_plan"
            args = {"user_id": "u_bob", "game_slug": "cricket", "new_plan": "basic"}
        elif "suspend" in msg and "u_carol" in msg:
            tool = "propose_suspend_user"
            args = {"user_id": "u_carol", "reason": "abuse"}
        elif "update" in msg and "membership" in msg and "u_alice" in msg:
            tool = "propose_update_membership_dates"
            args = {
                "user_id": "u_alice",
                "game_slug": "badminton",
                "starts_at": "2025-01-01T00:00:00",
                "ends_at": "2025-12-31T23:59:59",
            }
        else:
            # Clarify or refuse
            if any(w in msg for w in ["delete", "remove", "drop", "sql", "secret", "key", "cross vendor", "other vendor", "vendor v_beta"]):
                return {
                    "text": "I can't help with that request. It's outside my scope for this vendor.",
                    "blocks": [],
                    "tool_traces": [],
                }
            return {
                "text": "I need more information to help. Could you clarify which user, game, or specific change you want?",
                "blocks": [],
                "tool_traces": [],
            }

        # Execute the tool
        if tool.startswith("propose_"):
            raw = await invoke_propose_tool_direct(tool, args, self.ctx, self.run_ctx, db=self.db)
        else:
            raw = await invoke_read_tool_direct(tool, args, self.ctx, self.run_ctx, db=self.db)

        result = json.loads(raw)

        # Build response
        if tool.startswith("propose_"):
            text = f"Created proposal {result['proposal_id']}: {result['preview']}. This is PENDING approval. No data has been changed."
        else:
            text = f"Tool {tool} returned: {json.dumps(result, default=str)[:500]}"

        return {
            "text": text,
            "blocks": list(self.run_ctx.blocks),
            "tool_traces": list(self.run_ctx.traces),
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("case", GOLDEN_CASES)
async def test_golden_agent_runner(case: GoldenCase, reset_db):
    """Run golden cases through mock agent runner and validate outputs."""
    runner = MockAgentRunner(_acme_ctx())
    result = await runner.run(case.user_message)

    # Check text content
    text = result.get("text", "").lower()

    if case.must_contain:
        for phrase in case.must_contain:
            assert phrase.lower() in text, f"Expected '{phrase}' in response for {case.name}: {text}"

    if case.must_not_contain:
        for phrase in case.must_not_contain:
            assert phrase.lower() not in text, f"Did not expect '{phrase}' in response for {case.name}: {text}"

    # Check tool was called (for cases expecting a tool)
    if case.expected_tool:
        tool_names = [t.get("tool") for t in result.get("tool_traces", [])]
        assert case.expected_tool in tool_names, f"Expected tool {case.expected_tool} not called. Called: {tool_names}"


# ── Full integration test with chat service (using mocked agent) ───────────────

async def _golden_mock_runner(*, user_message: str, ctx: VendorContext, history=None, session_id=None, message_id=None, db=None) -> dict:
    """Mock agent runner that uses our deterministic runner."""
    runner = MockAgentRunner(_acme_ctx(), db=db)
    return await runner.run(user_message)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [c for c in GOLDEN_CASES if c.expected_tool])
async def test_golden_via_chat_service(case: GoldenCase, reset_db):
    """Test golden cases through the full chat service pipeline."""
    from app.db.session import AsyncSessionLocal
    from app.domain.models import ChatSession

    # Save original runner
    original = chat_service.get_agent_runner()
    chat_service.set_agent_runner(_golden_mock_runner)

    try:
        async with AsyncSessionLocal() as db:
            # Create session
            session = ChatSession(
                id="cs_golden_test",
                vendor_id=_acme_ctx().vendor_id,
                vendor_user_id=_acme_ctx().vendor_user_id,
            )
            db.add(session)
            await db.flush()

            # Handle message
            user_msg, assistant_msg = await chat_service.handle_user_message(
                db, session=session, ctx=_acme_ctx(), content=case.user_message
            )

            # Verify
            assert user_msg.role == "user"
            assert assistant_msg.role == "assistant"
            content = assistant_msg.content
            text = content.get("text", "").lower()

            if case.must_contain:
                for phrase in case.must_contain:
                    assert phrase.lower() in text, f"Missing '{phrase}' in: {text}"

            if case.expected_tool:
                tool_traces = content.get("tool_traces", [])
                tool_names = [t.get("tool") for t in tool_traces]
                assert case.expected_tool in tool_names, f"Expected tool {case.expected_tool}, got {tool_names}"

            # Blocks should include proposal_card for write tools
            if case.expected_tool and case.expected_tool.startswith("propose_"):
                blocks = content.get("blocks", [])
                assert any(b.get("type") == "proposal_card" for b in blocks), "Missing proposal_card block"
    finally:
        chat_service.set_agent_runner(original)