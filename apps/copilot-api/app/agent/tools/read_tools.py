"""Vendor-scoped read tools for the copilot agent.

``vendor_id`` is always taken from ``VendorContext`` — never from tool args.

Tools are CrewAI ``BaseTool`` subclasses with explicit Pydantic args schemas.

``_run`` is async. CrewAI's async agent path (``kickoff_async`` → ``ainvoke``)
awaits coroutine tools on the same event loop, which is what FastAPI needs.

The sync entrypoint ``BaseTool.run`` / structured ``invoke`` may still call
``asyncio.run``; ``run_coro_sync`` bridges that without nest_asyncio, using a
dedicated short-lived engine so asyncpg connections are never shared across
event loops.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, Optional

from crewai.tools.base_tool import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tools.async_bridge import run_coro_sync
from app.agent.tools.registry import ToolRunContext
from app.agent.tools.rbac import check_tool_permission, ALL_TOOL_PERMISSIONS
from app.config import get_settings
from app.domain.repos.games import GamesRepo
from app.domain.repos.memberships import MembershipsRepo
from app.domain.repos.revenue import RevenueRepo
from app.domain.repos.users import UsersRepo
from app.domain.schemas import VendorContext


# ── Args schemas ─────────────────────────────────────────────────────────────

class _NoArgs(BaseModel):
    pass


class ListTrialUsersArgs(BaseModel):
    game_slug: Optional[str] = Field(None, description="Game slug filter, e.g. 'badminton'")
    limit: int = Field(20, description="Max rows (1-50)", ge=1, le=50)


class GetRevenueArgs(BaseModel):
    game_slug: Optional[str] = Field(None, description="Game slug; omit for all-games rollup")


class SearchUsersArgs(BaseModel):
    query: str = Field("", description="Email, name, or user id fragment. Leave empty to list all users.")
    limit: int = Field(20, description="Max rows (1-50)", ge=1, le=50)


class GetUserArgs(BaseModel):
    user_id: str = Field(..., description="App user id, e.g. u_alice")


class GetMembershipArgs(BaseModel):
    user_id: str = Field(..., description="App user id, e.g. u_alice")
    game_slug: str = Field(..., description="Game slug, e.g. badminton")


class GetVendorSummaryArgs(BaseModel):
    pass


# ── Isolated session (safe on any event loop) ────────────────────────────────

@asynccontextmanager
async def _tool_session():
    """Open a NullPool session bound to the *current* event loop, then dispose."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


# ── Tool base ────────────────────────────────────────────────────────────────

class _ReadToolBase(BaseTool):
    """Base for vendor-scoped read tools. Closes over ctx + run_ctx."""

    _ctx: Any = PrivateAttr(default=None)
    _run_ctx: Any = PrivateAttr(default=None)

    def _record(self, tool: str, args: dict, result: Any, block: dict | None = None) -> None:
        self._run_ctx.record(tool, args, result, block=block)

    def _check_permission(self) -> str | None:
        if not check_tool_permission(self.name, self._ctx.role):
            return json.dumps({
                "error": f"Role '{self._ctx.role}' not authorized to use tool '{self.name}'",
                "allowed_roles": list(ALL_TOOL_PERMISSIONS.get(self.name, set())),
            })
        return None

    def _sync_bridge(self, coro):
        """Sync CrewAI entry → async body (only used if sync invoke/run is hit)."""
        return run_coro_sync(coro)

    def to_structured_tool(self):
        """Expose async ``_execute`` so CrewAI ``ainvoke`` awaits on the request loop.

        Default BaseTool wiring binds ``func=self._run`` (sync bridge). That forces
        ``ainvoke`` into a thread-pool executor, which breaks asyncpg pools.
        Binding the real async body keeps tool I/O on FastAPI's event loop.
        """
        from crewai.tools.structured_tool import CrewStructuredTool

        self._set_args_schema()
        structured = CrewStructuredTool(
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            result_schema=self.result_schema,
            func=self._execute,
            result_as_answer=self.result_as_answer,
            max_usage_count=self.max_usage_count,
            current_usage_count=self.current_usage_count,
            cache_function=self.cache_function,
        )
        structured._original_tool = self
        return structured


# ── Games ────────────────────────────────────────────────────────────────────

class ListGamesTool(_ReadToolBase):
    name: str = "list_games"
    description: str = "List games owned by the current vendor. No arguments."
    args_schema: type[BaseModel] = _NoArgs

    def _run(self) -> str:
        # Sync fallback for BaseTool.run / structured invoke
        return self._sync_bridge(self._execute())

    async def _arun(self) -> str:
        return await self._execute()

    async def _execute(self) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            rows = await GamesRepo(session).list_games(vendor_id=self._ctx.vendor_id)
        self._record(
            "list_games",
            {},
            rows,
            block={
                "type": "table",
                "title": "Games",
                "columns": ["id", "slug", "name"],
                "rows": [[r["id"], r["slug"], r["name"]] for r in rows],
            }
            if rows
            else None,
        )
        return json.dumps({"games": rows, "count": len(rows)})


# ── Trial users ──────────────────────────────────────────────────────────────

class ListTrialUsersTool(_ReadToolBase):
    name: str = "list_trial_users"
    description: str = (
        "List users currently on an active free trial. "
        "Optional game_slug filter; limit max rows (1-50)."
    )
    args_schema: type[BaseModel] = ListTrialUsersArgs

    def _run(self, game_slug: Optional[str] = None, limit: int = 20) -> str:
        return self._sync_bridge(self._execute(game_slug=game_slug, limit=limit))

    async def _arun(self, game_slug: Optional[str] = None, limit: int = 20) -> str:
        return await self._execute(game_slug=game_slug, limit=limit)

    async def _execute(self, game_slug: Optional[str] = None, limit: int = 20) -> str:
        if err := self._check_permission():
            return err
        limit = max(1, min(int(limit or 20), 50))
        async with _tool_session() as session:
            rows = await MembershipsRepo(session).list_trials(
                vendor_id=self._ctx.vendor_id, game_slug=game_slug, limit=limit
            )
        args = {"game_slug": game_slug, "limit": limit}
        self._record(
            "list_trial_users",
            args,
            rows,
            block={
                "type": "table",
                "title": f"Trial users{f' · {game_slug}' if game_slug else ''}",
                "columns": [
                    "user_id",
                    "display_name",
                    "email",
                    "game_slug",
                    "trial_ends_at",
                ],
                "rows": [
                    [
                        r["user_id"],
                        r["display_name"],
                        r["email"],
                        r["game_slug"],
                        r["trial_ends_at"],
                    ]
                    for r in rows
                ],
            }
            if rows
            else None,
        )
        return json.dumps({"trial_users": rows, "count": len(rows)})


# ── Revenue ──────────────────────────────────────────────────────────────────

class GetRevenueTool(_ReadToolBase):
    name: str = "get_revenue"
    description: str = (
        "Get revenue for TODAY (resolved server-side in the vendor's timezone). "
        "Optional game_slug filter; omit it for the all-games rollup. "
        "Never pass a date — the tool always uses today."
    )
    args_schema: type[BaseModel] = GetRevenueArgs

    def _run(self, game_slug: Optional[str] = None) -> str:
        return self._sync_bridge(self._execute(game_slug=game_slug))

    async def _arun(self, game_slug: Optional[str] = None) -> str:
        return await self._execute(game_slug=game_slug)

    async def _execute(self, game_slug: Optional[str] = None) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            result = await RevenueRepo(session).get_revenue(
                vendor_id=self._ctx.vendor_id,
                day=None,
                game_slug=game_slug,
                timezone_name=self._ctx.timezone,
            )
        args = {"game_slug": game_slug}
        self._record(
            "get_revenue",
            args,
            result,
            block={
                "type": "kpi",
                "title": f"Revenue · {result.get('day')}",
                "metrics": {
                    "net": result.get("net"),
                    "gross": result.get("gross"),
                    "refunds": result.get("refunds"),
                    "currency": result.get("currency", "USD"),
                    "game_slug": result.get("game_slug"),
                },
            }
            if result.get("found")
            else None,
        )
        return json.dumps(result)


# ── Search users ─────────────────────────────────────────────────────────────

class SearchUsersTool(_ReadToolBase):
    name: str = "search_users"
    description: str = (
        "Search end-users by id, email, or display name (current vendor only). "
        "Can also be used to list all users by leaving the query empty."
    )
    args_schema: type[BaseModel] = SearchUsersArgs

    def _run(self, query: str = "", limit: int = 20) -> str:
        return self._sync_bridge(self._execute(query=query, limit=limit))

    async def _arun(self, query: str = "", limit: int = 20) -> str:
        return await self._execute(query=query, limit=limit)

    async def _execute(self, query: str = "", limit: int = 20) -> str:
        if err := self._check_permission():
            return err
        limit = max(1, min(int(limit or 20), 50))
        async with _tool_session() as session:
            rows = await UsersRepo(session).search(
                vendor_id=self._ctx.vendor_id, query=query, limit=limit
            )
        args = {"query": query, "limit": limit}
        self._record(
            "search_users",
            args,
            rows,
            block={
                "type": "table",
                "title": f"Users matching '{query}'" if query else "All users",
                "columns": ["id", "display_name", "email", "status"],
                "rows": [
                    [r["id"], r["display_name"], r["email"], r["status"]] for r in rows
                ],
            }
            if rows
            else None,
        )
        return json.dumps({"users": rows, "count": len(rows)})


# ── Get user ─────────────────────────────────────────────────────────────────

class GetUserTool(_ReadToolBase):
    name: str = "get_user"
    description: str = (
        "Get a single end-user profile and their memberships (current vendor only)."
    )
    args_schema: type[BaseModel] = GetUserArgs

    def _run(self, user_id: str) -> str:
        return self._sync_bridge(self._execute(user_id=user_id))

    async def _arun(self, user_id: str) -> str:
        return await self._execute(user_id=user_id)

    async def _execute(self, user_id: str) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            user = await UsersRepo(session).get_user(
                vendor_id=self._ctx.vendor_id, user_id=user_id
            )
        self._record("get_user", {"user_id": user_id}, user)
        if user is None:
            return json.dumps({"found": False, "error": f"User '{user_id}' not found"})
        return json.dumps({"found": True, "user": user})


# ── Get membership ───────────────────────────────────────────────────────────

class GetMembershipTool(_ReadToolBase):
    name: str = "get_membership"
    description: str = (
        "Get membership detail for a user + game (current vendor only)."
    )
    args_schema: type[BaseModel] = GetMembershipArgs

    def _run(self, user_id: str, game_slug: str) -> str:
        return self._sync_bridge(self._execute(user_id=user_id, game_slug=game_slug))

    async def _arun(self, user_id: str, game_slug: str) -> str:
        return await self._execute(user_id=user_id, game_slug=game_slug)

    async def _execute(self, user_id: str, game_slug: str) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            m = await MembershipsRepo(session).get_membership(
                vendor_id=self._ctx.vendor_id,
                user_id=user_id,
                game_slug=game_slug,
            )
        self._record(
            "get_membership", {"user_id": user_id, "game_slug": game_slug}, m
        )
        if m is None:
            return json.dumps(
                {
                    "found": False,
                    "error": f"No membership for user '{user_id}' on game '{game_slug}'",
                }
            )
        return json.dumps({"found": True, "membership": m})


# ── Vendor summary ───────────────────────────────────────────────────────────

class GetVendorSummaryTool(_ReadToolBase):
    name: str = "get_vendor_summary"
    description: str = (
        "High-level KPIs for the current vendor: active users, active trials, "
        "game count, and TODAY's revenue (resolved server-side). No arguments."
    )
    args_schema: type[BaseModel] = GetVendorSummaryArgs

    def _run(self) -> str:
        return self._sync_bridge(self._execute())

    async def _arun(self) -> str:
        return await self._execute()

    async def _execute(self) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            summary = await RevenueRepo(session).vendor_summary(
                vendor_id=self._ctx.vendor_id,
                day=None,
                timezone_name=self._ctx.timezone,
            )
        self._record(
            "get_vendor_summary",
            {},
            summary,
            block={
                "type": "kpi",
                "title": f"Vendor summary · {summary.get('day')}",
                "metrics": {
                    "active_users": summary.get("active_users"),
                    "active_trials": summary.get("active_trials"),
                    "game_count": summary.get("game_count"),
                    "net_revenue": (summary.get("revenue") or {}).get("net"),
                },
            },
        )
        return json.dumps(summary)


_TOOL_CLASSES = [
    ListGamesTool,
    ListTrialUsersTool,
    GetRevenueTool,
    SearchUsersTool,
    GetUserTool,
    GetMembershipTool,
    GetVendorSummaryTool,
]


def build_read_tools(ctx: VendorContext, run_ctx: ToolRunContext, db=None) -> list[BaseTool]:
    """Build CrewAI tools closed over the authenticated vendor context.

    ``db`` is accepted for API compatibility but ignored — tools open their
    own NullPool sessions so they are safe across event-loop boundaries.
    """
    del db
    tools: list[BaseTool] = []
    for cls in _TOOL_CLASSES:
        instance = cls()
        instance._ctx = ctx
        instance._run_ctx = run_ctx
        tools.append(instance)
    return tools


async def invoke_read_tool_direct(
    name: str,
    args: dict[str, Any],
    ctx: VendorContext,
    run_ctx: ToolRunContext | None = None,
    db=None,
) -> str:
    """Call a read tool by name without the agent (tests / deterministic path)."""
    del db
    run_ctx = run_ctx or ToolRunContext()
    tools = {t.name: t for t in build_read_tools(ctx, run_ctx)}
    if name not in tools:
        raise KeyError(f"Unknown tool: {name}")
    return await tools[name]._execute(**args)
