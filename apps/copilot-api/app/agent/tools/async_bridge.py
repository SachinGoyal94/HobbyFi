"""Run async tool bodies safely from CrewAI's sync tool entrypoints.

CrewAI converts BaseTool → CrewStructuredTool with ``func=self._run`` and may
call either:

* ``ainvoke`` (async agent path) — fine for async funcs via ``await``
* ``invoke`` / ``BaseTool.run`` (sync path) — uses ``asyncio.run(coro)``

Inside FastAPI there is already a running event loop, so bare ``asyncio.run``
raises. ``nest_asyncio`` re-enters the loop but breaks asyncpg connections
("Future attached to a different loop").

Solution: when a loop is already running, execute the coroutine in a **new
thread with its own event loop**. Tool code must open its **own** DB session
in that path (never share the request-scoped AsyncSession across loops).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")

# Bound tool runtime so a hung DB call cannot freeze the agent forever.
_DEFAULT_TIMEOUT_S = 60.0


def run_coro_sync(coro: Coroutine[object, object, T], *, timeout: float = _DEFAULT_TIMEOUT_S) -> T:
    """Block until *coro* finishes; safe from sync or already-async contexts."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — normal asyncio.run is fine.
        return asyncio.run(coro)

    # Already inside an event loop (FastAPI / pytest-asyncio / nest). Isolate.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result(timeout=timeout)
