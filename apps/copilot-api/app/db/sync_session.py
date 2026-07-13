"""Sync SQLAlchemy session for CrewAI tools (agent runtime is synchronous).

FastAPI routes keep using the async engine. Tools open short-lived sync
sessions so they never share an event loop with the request handler.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings, to_sync_database_url

_settings = get_settings()


sync_engine = create_engine(
    to_sync_database_url(_settings.database_url),
    echo=_settings.app_env == "development",
    connect_args={"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {},
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)
