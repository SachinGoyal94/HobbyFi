"""Shared fixtures for copilot API tests."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "copilot-api"))

# Point .env to the project root so Settings finds GEMINI_API_KEY
os.environ.setdefault("GEMINI_API_KEY", "test-fixture-key")

from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.domain.models import Base  # noqa: E402
from app.domain.seed import seed_mock_data  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import chat_service  # noqa: E402


def _mock_agent_runner(*, user_message: str, ctx, history=None) -> dict:
    """Deterministic agent stub for API tests (no real Gemini / CrewAI)."""
    return {
        "text": f"Mock answer for: {user_message}",
        "blocks": [],
        "tool_traces": [],
    }


@pytest.fixture(autouse=True)
def mock_agent():
    """Replace agent runner for every test; restore after."""
    chat_service.set_agent_runner(_mock_agent_runner)
    yield
    chat_service.set_agent_runner(None)


@pytest.fixture(scope="session")
def app():
    """Create a single FastAPI app for all tests."""
    return create_app()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async httpx client using ASGI transport (no real HTTP needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def reset_db() -> AsyncGenerator[None, None]:
    """Reset tables + seed before each test."""
    # Drop all tables — NOT inside a transaction (SQLite can't rollback DDL)
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()

    # Seed
    async with AsyncSessionLocal() as session:
        await seed_mock_data(session)
        await session.commit()

    yield

    # Cleanup
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.commit()


# ── Auth header helper ────────────────────────────────────────────────────────


def auth_headers(
    vendor_id: str = "v_acme",
    user_id: str = "vu_admin",
    role: str = "admin",
) -> dict[str, str]:
    return {
        "x-vendor-id": vendor_id,
        "x-vendor-user-id": user_id,
        "x-vendor-role": role,
    }
