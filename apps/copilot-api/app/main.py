"""FastAPI application factory for the Vendor Portal Copilot API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.request_id import RequestIDMiddleware
from app.api.rate_limiter import add_rate_limit_headers
from app.api.routes import health, proposals, sessions, utility
from app.config import get_settings
from app.db.session import engine
from app.domain.models import Base
from app.domain.seed import seed_mock_data
from app.observability import LoggingMiddleware, setup_structured_logging
from app.services.proposal_expiry import start_expiry_task, stop_expiry_task


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create tables and seed mock data on startup; dispose engine on shutdown."""
    settings = get_settings()

    # Setup structured logging
    setup_structured_logging(settings.log_level)

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

    # Start background proposal expiry task
    from app.services.proposal_expiry import start_expiry_task, stop_expiry_task

    start_expiry_task(interval_seconds=60)

    try:
        yield
    finally:
        await stop_expiry_task()
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

    # Structured logging and correlation IDs
    app.add_middleware(LoggingMiddleware)

    # Rate limit headers on all responses
    app.middleware("http")(add_rate_limit_headers)

    # Routes
    app.include_router(health.router, tags=["Health"])
    app.include_router(sessions.router, prefix="/v1/copilot", tags=["Chat"])
    app.include_router(proposals.router, prefix="/v1/copilot/proposals", tags=["Approvals"])
    app.include_router(utility.router, tags=["Admin"])

    return app


app = create_app()