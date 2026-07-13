"""Shared fixtures for copilot API tests."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

# Ensure app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "copilot-api"))

# Point .env to the project root so Settings finds GEMINI_API_KEY
os.environ.setdefault("GEMINI_API_KEY", "test-fixture-key")

from app.config import get_settings, to_sync_database_url  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.domain.models import Base  # noqa: E402
from app.domain.seed import seed_mock_data_sync  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import chat_service  # noqa: E402


async def _mock_agent_runner(*, user_message: str, ctx, history=None, session_id=None, message_id=None, db=None) -> dict:
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


# ── Sync DB helpers (schema / truncate / seed have no event-loop coupling) ───

_TABLES = (
    "chat_messages",
    "chat_sessions",
    "action_proposals",
    "audit_events",
    "memberships",
    "app_users",
    "games",
    "vendor_users",
    "vendors",
    "revenue_daily",
)

_schema_created = False
_sync_engine = None
_SyncSessionLocal = None


def _get_sync_session_factory():
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        settings = get_settings()
        _sync_engine = create_sync_engine(to_sync_database_url(settings.database_url))
        _SyncSessionLocal = sessionmaker(
            bind=_sync_engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sync_engine, _SyncSessionLocal


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, None, None]:
    """Create schema once, then truncate + reseed before each test (all sync)."""
    global _schema_created

    sync_engine, SessionLocal = _get_sync_session_factory()
    if not _schema_created:
        Base.metadata.create_all(sync_engine)
        _schema_created = True

    table_list = ", ".join(_TABLES)
    with sync_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))

    with SessionLocal() as session:
        seed_mock_data_sync(session)
        session.commit()

    yield


@pytest.fixture(scope="session", autouse=True)
async def _dispose_async_engine():
    """Dispose the async engine after the full suite (session-scoped loop)."""
    yield
    await engine.dispose()
    sync_engine, _ = _get_sync_session_factory()
    sync_engine.dispose()


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
