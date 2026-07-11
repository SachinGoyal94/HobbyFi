"""FastAPI application factory for the Vendor Portal Copilot API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.request_id import RequestIDMiddleware
from app.api.routes import health, sessions, utility
from app.config import get_settings
from app.db.session import engine
from app.domain.models import Base
from app.domain.seed import seed_mock_data


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create tables and seed mock data on startup; dispose engine on shutdown."""
    settings = get_settings()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed mock data (idempotent — no-op if already seeded)
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        counts = await seed_mock_data(session)
        await session.commit()

    if settings.app_env == "development":
        import logging

        logger = logging.getLogger("app.lifespan")
        logger.info("Mock data seed counts: %s", counts)

    yield

    await engine.dispose()


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID on every response
    app.add_middleware(RequestIDMiddleware)

    # Routes
    app.include_router(health.router, tags=["Health"])
    app.include_router(sessions.router, prefix="/v1/copilot", tags=["Chat"])
    app.include_router(utility.router, tags=["Admin"])

    return app


app = create_app()