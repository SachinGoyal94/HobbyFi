"""Background task to expire overdue proposals."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.db.session import AsyncSessionLocal
from app.services import approval_service

_log = logging.getLogger(__name__)

_expiry_task: Optional[asyncio.Task] = None


async def _expiry_loop(interval_seconds: int) -> None:
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with AsyncSessionLocal() as db:
                count = await approval_service.expire_overdue_proposals(db)
                if count:
                    await db.commit()
                    _log.info("Expired %d overdue proposals", count)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.exception("Proposal expiry task error: %s", exc)


def start_expiry_task(interval_seconds: int = 60) -> None:
    """Start the background task that expires overdue proposals."""
    global _expiry_task
    if _expiry_task is not None and not _expiry_task.done():
        return
    _expiry_task = asyncio.create_task(_expiry_loop(interval_seconds))
    _log.info("Proposal expiry task started (interval=%ds)", interval_seconds)


async def stop_expiry_task() -> None:
    """Stop the background expiry task."""
    global _expiry_task
    if _expiry_task is not None:
        _expiry_task.cancel()
        try:
            await _expiry_task
        except asyncio.CancelledError:
            pass
        _expiry_task = None
        _log.info("Proposal expiry task stopped")