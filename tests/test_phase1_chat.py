"""Phase 1 — chat turn API with mocked agent + SSE."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.agent.tools.read_tools import invoke_read_tool_direct
from app.agent.tools.registry import ToolRunContext
from app.domain.schemas import VendorContext
from app.services import chat_service
from conftest import auth_headers


@pytest.mark.asyncio
async def test_post_message_returns_turn_with_assistant(client: AsyncClient):
    headers = auth_headers()
    resp = await client.post("/v1/copilot/sessions", json={}, headers=headers)
    sid = resp.json()["id"]

    resp = await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "What is today's revenue?"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["session_id"] == sid
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"]["text"] == "What is today's revenue?"
    assert body["assistant_message"]["role"] == "assistant"
    assert "Mock answer" in body["assistant_message"]["content"]["text"]
    assert "blocks" in body["assistant_message"]["content"]


@pytest.mark.asyncio
async def test_agent_runner_receives_vendor_context(client: AsyncClient):
    seen: dict = {}

    async def runner(*, user_message: str, ctx: VendorContext, history=None, session_id=None, message_id=None, db=None):
        seen["vendor_id"] = ctx.vendor_id
        seen["message"] = user_message
        return {
            "text": f"Revenue for {ctx.vendor_name}",
            "blocks": [{"type": "kpi", "title": "test"}],
            "tool_traces": [{"tool": "get_revenue", "args": {}, "result": {}}],
        }

    chat_service.set_agent_runner(runner)

    headers = auth_headers()
    resp = await client.post("/v1/copilot/sessions", json={}, headers=headers)
    sid = resp.json()["id"]
    resp = await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "revenue today"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert seen["vendor_id"] == "v_acme"
    assert seen["message"] == "revenue today"
    content = resp.json()["assistant_message"]["content"]
    assert content["text"] == "Revenue for Acme Sports"
    assert content["blocks"][0]["type"] == "kpi"
    assert content["tool_traces"][0]["tool"] == "get_revenue"


@pytest.mark.asyncio
async def test_agent_error_still_returns_assistant_message(client: AsyncClient):
    async def boom(*, user_message: str, ctx, history=None, session_id=None, message_id=None):
        raise RuntimeError("gemini down")

    chat_service.set_agent_runner(boom)

    headers = auth_headers()
    resp = await client.post("/v1/copilot/sessions", json={}, headers=headers)
    sid = resp.json()["id"]
    resp = await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "hello"},
        headers=headers,
    )
    assert resp.status_code == 201
    text = resp.json()["assistant_message"]["content"]["text"]
    assert "error" in text.lower() or "Sorry" in text


@pytest.mark.asyncio
async def test_stream_endpoint_emits_sse_events(client: AsyncClient):
    headers = auth_headers()
    resp = await client.post("/v1/copilot/sessions", json={}, headers=headers)
    sid = resp.json()["id"]

    resp = await client.post(
        f"/v1/copilot/sessions/{sid}/messages:stream",
        json={"content": "list games"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    raw = resp.text
    assert "event: status" in raw
    assert "event: result" in raw
    assert "event: done" in raw
    assert "Mock answer" in raw


@pytest.mark.asyncio
async def test_tool_backed_agent_simulation(client: AsyncClient):
    """Simulate what the agent does: call real tools with vendor context."""

    async def tool_backed(*, user_message: str, ctx: VendorContext, history=None, session_id=None, message_id=None, db=None):
        run_ctx = ToolRunContext()
        if "trial" in user_message.lower() and "badminton" in user_message.lower():
            raw = await invoke_read_tool_direct(
                "list_trial_users",
                {"game_slug": "badminton"},
                ctx,
                run_ctx,
            )
            data = json.loads(raw)
            names = [u["display_name"] for u in data["trial_users"]]
            text = f"Found {data['count']} trial users: {', '.join(names)}"
        elif "revenue" in user_message.lower():
            raw = await invoke_read_tool_direct("get_revenue", {}, ctx, run_ctx)
            data = json.loads(raw)
            text = f"Today's net revenue is ${data.get('net', '0.00')}"
        else:
            text = "I can help with revenue, trials, users, and games."
        return {
            "text": text,
            "blocks": list(run_ctx.blocks),
            "tool_traces": list(run_ctx.traces),
        }

    chat_service.set_agent_runner(tool_backed)
    headers = auth_headers()
    resp = await client.post("/v1/copilot/sessions", json={}, headers=headers)
    sid = resp.json()["id"]

    resp = await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "List trial users of badminton game"},
        headers=headers,
    )
    body = resp.json()
    assert body["assistant_message"]["content"]["text"].startswith("Found 2 trial users")
    assert any(
        b["type"] == "table" for b in body["assistant_message"]["content"]["blocks"]
    )

    resp = await client.post(
        f"/v1/copilot/sessions/{sid}/messages",
        json={"content": "What is revenue of today?"},
        headers=headers,
    )
    text = resp.json()["assistant_message"]["content"]["text"]
    assert "$1285.00" in text
