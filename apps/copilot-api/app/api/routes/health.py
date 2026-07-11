"""Health-check endpoint — liveness + app metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import Settings, get_settings
from app.db.session import get_db

router = APIRouter()


@router.get("/v1/health")
async def health_check(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    """Liveness probe with app metadata and DB connectivity status."""
    db_ok = True
    db_type = "unknown"

    try:
        await db.execute(text("SELECT 1"))
        db_type = _db_label(settings.database_url)
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "env": settings.app_env,
        "version": __version__,
        "gemini_model": settings.gemini_model,
        "gemini_configured": bool(settings.gemini_api_key),
        "database": db_type if db_ok else "unreachable",
    }


def _db_label(url: str) -> str:
    if "sqlite" in url:
        return "sqlite"
    if "postgresql" in url or "postgres" in url:
        return "postgresql"
    return "other"