"""Vendor-scoped propose_* (write) tools for the copilot agent.

IMPORTANT: these tools NEVER mutate domain data. Each one builds a
``before``/``after`` preview and inserts a pending ``ActionProposal`` row.

Async execution model matches read_tools: ``_execute`` is the real async body,
``to_structured_tool`` exposes it to CrewAI's ``ainvoke``, and sync ``_run`` is
a NullPool-safe bridge for rare sync callers.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from crewai.tools.base_tool import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tools.async_bridge import run_coro_sync
from app.agent.tools.registry import ToolRunContext
from app.agent.tools.rbac import check_tool_permission
from app.config import get_settings
from app.domain.models import ActionProposal, AuditEvent
from app.domain.repos.memberships import MembershipsRepo
from app.domain.repos.users import UsersRepo
from app.domain.schemas import VendorContext

_settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _make_proposal(
    *,
    ctx: VendorContext,
    action_type: str,
    payload: dict[str, Any],
    preview: dict[str, Any],
    session_id: str | None = None,
    message_id: str | None = None,
) -> ActionProposal:
    now = _utcnow()
    return ActionProposal(
        id=_new_id("ap"),
        vendor_id=ctx.vendor_id,
        session_id=session_id,
        message_id=message_id,
        proposed_by=ctx.vendor_user_id,
        action_type=action_type,
        payload=payload,
        preview=preview,
        status="pending",
        idempotency_key=_new_id("idem"),
        expires_at=now + timedelta(minutes=_settings.proposal_ttl_minutes),
        created_at=now,
    )


@asynccontextmanager
async def _tool_session():
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
    )
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
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


# ── Args schemas ─────────────────────────────────────────────────────────────

class ExtendTrialArgs(BaseModel):
    user_id: str = Field(..., description="App user id, e.g. u_alice")
    game_slug: str = Field(..., description="Game slug, e.g. badminton")
    extra_days: int = Field(..., description="Days to add to the trial", ge=1, le=90)


class UpdateMembershipDatesArgs(BaseModel):
    user_id: str = Field(..., description="App user id, e.g. u_alice")
    game_slug: str = Field(..., description="Game slug, e.g. badminton")
    starts_at: Optional[str] = Field(None, description="ISO datetime to set start")
    ends_at: Optional[str] = Field(None, description="ISO datetime to set end")


class ChangePlanArgs(BaseModel):
    user_id: str = Field(..., description="App user id, e.g. u_alice")
    game_slug: str = Field(..., description="Game slug, e.g. badminton")
    new_plan: str = Field(..., description="free | trial | basic | pro")


class SuspendUserArgs(BaseModel):
    user_id: str = Field(..., description="App user id, e.g. u_alice")
    reason: str = Field(..., description="Reason for suspension (for audit)")


# ── Tool base ────────────────────────────────────────────────────────────────

class _WriteToolBase(BaseTool):
    _ctx: Any = PrivateAttr(default=None)
    _run_ctx: Any = PrivateAttr(default=None)
    _session_id: Optional[str] = PrivateAttr(default=None)
    _message_id: Optional[str] = PrivateAttr(default=None)

    def _check_permission(self) -> str | None:
        if not check_tool_permission(self.name, self._ctx.role):
            return json.dumps({
                "error": f"Role '{self._ctx.role}' not authorized to use tool '{self.name}'",
            })
        return None

    def _sync_bridge(self, coro):
        return run_coro_sync(coro)

    def to_structured_tool(self):
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

    def _emit(self, proposal: ActionProposal, preview: dict[str, Any]) -> str:
        self._run_ctx.record(
            f"propose_{proposal.action_type}",
            proposal.payload,
            {"proposal_id": proposal.id, "preview": preview},
            block={
                "type": "proposal_card",
                "proposal_id": proposal.id,
                "action_type": proposal.action_type,
                "status": proposal.status,
                "preview": preview,
                "expires_at": proposal.expires_at.isoformat(),
            },
        )
        return json.dumps(
            {
                "proposal_id": proposal.id,
                "action_type": proposal.action_type,
                "status": proposal.status,
                "preview": preview,
                "expires_at": proposal.expires_at.isoformat(),
                "note": "Awaiting vendor approval. No data has been changed.",
            }
        )


# ── extend_trial ─────────────────────────────────────────────────────────────

class ProposeExtendTrialTool(_WriteToolBase):
    name: str = "propose_extend_trial"
    description: str = (
        "Propose adding N days to a user's free trial (does NOT change data; "
        "creates a pending approval). Args: user_id, game_slug, extra_days (1-90)."
    )
    args_schema: type[BaseModel] = ExtendTrialArgs

    def _run(self, user_id: str, game_slug: str, extra_days: int) -> str:
        return self._sync_bridge(
            self._execute(user_id=user_id, game_slug=game_slug, extra_days=extra_days)
        )

    async def _arun(self, user_id: str, game_slug: str, extra_days: int) -> str:
        return await self._execute(
            user_id=user_id, game_slug=game_slug, extra_days=extra_days
        )

    async def _execute(self, user_id: str, game_slug: str, extra_days: int) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            m = await MembershipsRepo(session).get_membership(
                vendor_id=self._ctx.vendor_id, user_id=user_id, game_slug=game_slug
            )
            if m is None:
                return json.dumps(
                    {"error": f"No membership for user '{user_id}' on '{game_slug}'"}
                )
            current = m.get("trial_ends_at")
            base = _parse_dt(current) if current else _utcnow()
            if base is not None and base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            new_trial_ends = (base or _utcnow()) + timedelta(days=int(extra_days))
            preview = {
                "user_id": user_id,
                "game_slug": game_slug,
                "before": {"trial_ends_at": current},
                "after": {"trial_ends_at": new_trial_ends.isoformat()},
                "extra_days": int(extra_days),
            }
            payload = {
                "user_id": user_id,
                "game_slug": game_slug,
                "extra_days": int(extra_days),
                "current_trial_ends_at": current,
                "new_trial_ends_at": new_trial_ends.isoformat(),
            }
            proposal = _make_proposal(
                ctx=self._ctx,
                action_type="extend_trial",
                payload=payload,
                preview=preview,
                session_id=self._session_id,
                message_id=self._message_id,
            )
            session.add(proposal)
            session.add(
                AuditEvent(
                    id=_new_id("ae"),
                    vendor_id=self._ctx.vendor_id,
                    actor_id=self._ctx.vendor_user_id,
                    event_type="proposal.create",
                    entity_type="action_proposal",
                    entity_id=proposal.id,
                    metadata_json={"action_type": "extend_trial", "payload": payload},
                    created_at=_utcnow(),
                )
            )
            return self._emit(proposal, preview)


# ── update_membership_dates ──────────────────────────────────────────────────

class ProposeUpdateMembershipDatesTool(_WriteToolBase):
    name: str = "propose_update_membership_dates"
    description: str = (
        "Propose setting a membership's start/end dates (pending approval). "
        "Args: user_id, game_slug, optional starts_at/ends_at (ISO datetime)."
    )
    args_schema: type[BaseModel] = UpdateMembershipDatesArgs

    def _run(
        self,
        user_id: str,
        game_slug: str,
        starts_at: Optional[str] = None,
        ends_at: Optional[str] = None,
    ) -> str:
        return self._sync_bridge(
            self._execute(
                user_id=user_id,
                game_slug=game_slug,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )

    async def _arun(
        self,
        user_id: str,
        game_slug: str,
        starts_at: Optional[str] = None,
        ends_at: Optional[str] = None,
    ) -> str:
        return await self._execute(
            user_id=user_id,
            game_slug=game_slug,
            starts_at=starts_at,
            ends_at=ends_at,
        )

    async def _execute(
        self,
        user_id: str,
        game_slug: str,
        starts_at: Optional[str] = None,
        ends_at: Optional[str] = None,
    ) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            m = await MembershipsRepo(session).get_membership(
                vendor_id=self._ctx.vendor_id, user_id=user_id, game_slug=game_slug
            )
            if m is None:
                return json.dumps(
                    {"error": f"No membership for user '{user_id}' on '{game_slug}'"}
                )
            before = {
                "starts_at": m.get("starts_at"),
                "ends_at": m.get("ends_at"),
            }
            new_start = _parse_dt(starts_at) if starts_at else _parse_dt(m.get("starts_at"))
            new_end = _parse_dt(ends_at) if ends_at else _parse_dt(m.get("ends_at"))
            preview = {
                "user_id": user_id,
                "game_slug": game_slug,
                "before": before,
                "after": {
                    "starts_at": new_start.isoformat() if new_start else None,
                    "ends_at": new_end.isoformat() if new_end else None,
                },
            }
            payload = {
                "user_id": user_id,
                "game_slug": game_slug,
                "starts_at": new_start.isoformat() if new_start else None,
                "ends_at": new_end.isoformat() if new_end else None,
            }
            proposal = _make_proposal(
                ctx=self._ctx,
                action_type="update_membership_dates",
                payload=payload,
                preview=preview,
                session_id=self._session_id,
                message_id=self._message_id,
            )
            session.add(proposal)
            session.add(
                AuditEvent(
                    id=_new_id("ae"),
                    vendor_id=self._ctx.vendor_id,
                    actor_id=self._ctx.vendor_user_id,
                    event_type="proposal.create",
                    entity_type="action_proposal",
                    entity_id=proposal.id,
                    metadata_json={
                        "action_type": "update_membership_dates",
                        "payload": payload,
                    },
                    created_at=_utcnow(),
                )
            )
            return self._emit(proposal, preview)


# ── change_plan ──────────────────────────────────────────────────────────────

class ProposeChangePlanTool(_WriteToolBase):
    name: str = "propose_change_plan"
    description: str = (
        "Propose changing a user's membership plan (pending approval). "
        "Args: user_id, game_slug, new_plan (free|trial|basic|pro)."
    )
    args_schema: type[BaseModel] = ChangePlanArgs

    def _run(self, user_id: str, game_slug: str, new_plan: str) -> str:
        return self._sync_bridge(
            self._execute(user_id=user_id, game_slug=game_slug, new_plan=new_plan)
        )

    async def _arun(self, user_id: str, game_slug: str, new_plan: str) -> str:
        return await self._execute(
            user_id=user_id, game_slug=game_slug, new_plan=new_plan
        )

    async def _execute(self, user_id: str, game_slug: str, new_plan: str) -> str:
        if err := self._check_permission():
            return err
        new_plan = (new_plan or "").strip().lower()
        if new_plan not in ("free", "trial", "basic", "pro"):
            return json.dumps(
                {"error": "new_plan must be one of free|trial|basic|pro"}
            )
        async with _tool_session() as session:
            m = await MembershipsRepo(session).get_membership(
                vendor_id=self._ctx.vendor_id, user_id=user_id, game_slug=game_slug
            )
            if m is None:
                return json.dumps(
                    {"error": f"No membership for user '{user_id}' on '{game_slug}'"}
                )
            preview = {
                "user_id": user_id,
                "game_slug": game_slug,
                "before": {"plan": m.get("plan")},
                "after": {"plan": new_plan},
            }
            payload = {
                "user_id": user_id,
                "game_slug": game_slug,
                "new_plan": new_plan,
                "current_plan": m.get("plan"),
            }
            proposal = _make_proposal(
                ctx=self._ctx,
                action_type="change_plan",
                payload=payload,
                preview=preview,
                session_id=self._session_id,
                message_id=self._message_id,
            )
            session.add(proposal)
            session.add(
                AuditEvent(
                    id=_new_id("ae"),
                    vendor_id=self._ctx.vendor_id,
                    actor_id=self._ctx.vendor_user_id,
                    event_type="proposal.create",
                    entity_type="action_proposal",
                    entity_id=proposal.id,
                    metadata_json={"action_type": "change_plan", "payload": payload},
                    created_at=_utcnow(),
                )
            )
            return self._emit(proposal, preview)


# ── suspend_user ─────────────────────────────────────────────────────────────

class ProposeSuspendUserTool(_WriteToolBase):
    name: str = "propose_suspend_user"
    description: str = (
        "Propose suspending an end-user account (pending approval). "
        "Args: user_id, reason."
    )
    args_schema: type[BaseModel] = SuspendUserArgs

    def _run(self, user_id: str, reason: str) -> str:
        return self._sync_bridge(self._execute(user_id=user_id, reason=reason))

    async def _arun(self, user_id: str, reason: str) -> str:
        return await self._execute(user_id=user_id, reason=reason)

    async def _execute(self, user_id: str, reason: str) -> str:
        if err := self._check_permission():
            return err
        async with _tool_session() as session:
            u = await UsersRepo(session).get_user(
                vendor_id=self._ctx.vendor_id, user_id=user_id
            )
            if u is None:
                return json.dumps({"error": f"User '{user_id}' not found"})
            preview = {
                "user_id": user_id,
                "before": {"status": u.get("status")},
                "after": {"status": "suspended"},
                "reason": reason,
            }
            payload = {
                "user_id": user_id,
                "reason": reason,
                "current_status": u.get("status"),
            }
            proposal = _make_proposal(
                ctx=self._ctx,
                action_type="suspend_user",
                payload=payload,
                preview=preview,
                session_id=self._session_id,
                message_id=self._message_id,
            )
            session.add(proposal)
            session.add(
                AuditEvent(
                    id=_new_id("ae"),
                    vendor_id=self._ctx.vendor_id,
                    actor_id=self._ctx.vendor_user_id,
                    event_type="proposal.create",
                    entity_type="action_proposal",
                    entity_id=proposal.id,
                    metadata_json={"action_type": "suspend_user", "payload": payload},
                    created_at=_utcnow(),
                )
            )
            return self._emit(proposal, preview)


_WRITE_TOOL_CLASSES = [
    ProposeExtendTrialTool,
    ProposeUpdateMembershipDatesTool,
    ProposeChangePlanTool,
    ProposeSuspendUserTool,
]


def build_write_tools(
    ctx: VendorContext,
    run_ctx: ToolRunContext,
    *,
    session_id: str | None = None,
    message_id: str | None = None,
    db=None,
) -> list[BaseTool]:
    del db
    tools: list[BaseTool] = []
    for cls in _WRITE_TOOL_CLASSES:
        instance = cls()
        instance._ctx = ctx
        instance._run_ctx = run_ctx
        instance._session_id = session_id
        instance._message_id = message_id
        tools.append(instance)
    return tools


async def invoke_propose_tool_direct(
    action: str,
    args: dict[str, Any],
    ctx: VendorContext,
    run_ctx: ToolRunContext | None = None,
    *,
    session_id: str | None = None,
    message_id: str | None = None,
    db=None,
) -> str:
    del db
    run_ctx = run_ctx or ToolRunContext()
    tools = {
        t.name: t
        for t in build_write_tools(
            ctx, run_ctx, session_id=session_id, message_id=message_id
        )
    }
    if action not in tools:
        raise KeyError(f"Unknown propose tool: {action}")
    return await tools[action]._execute(**args)
