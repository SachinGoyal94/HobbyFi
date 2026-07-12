"""Vendor-scoped propose_* (write) tools for the copilot agent.

IMPORTANT (plan §2 / §5.2): these tools NEVER mutate domain data. Each one
builds a ``before``/``after`` preview from current state and inserts a pending
``ActionProposal`` row. Execution happens later, server-side, only after a
vendor approves via the authenticated FastAPI decide endpoint — the LLM can
never call that endpoint (see approval_service + proposals routes).

Tools are CrewAI ``BaseTool`` subclasses with explicit Pydantic args schemas
(same approach as read_tools to avoid the Pydantic 2.12 schema-build issue).
``vendor_id`` is always taken from ``VendorContext``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from crewai.tools.base_tool import BaseTool
from pydantic import BaseModel, Field

from app.agent.tools.registry import ToolRunContext
from app.config import get_settings
from app.db.sync_session import SyncSessionLocal
from app.domain.models import ActionProposal, AuditEvent, Membership
from app.domain.repos.memberships import MembershipsRepo
from app.domain.repos.users import UsersRepo
from app.domain.schemas import VendorContext

_settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _proposal_payload(
    *,
    ctx: VendorContext,
    action_type: str,
    payload: dict[str, Any],
    preview: dict[str, Any],
    run_ctx: ToolRunContext,
    session_id: str | None = None,
    message_id: str | None = None,
) -> ActionProposal:
    """Insert a pending proposal and record an audit event. Caller commits."""
    now = _utcnow()
    proposal = ActionProposal(
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
    return proposal


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
    _ctx: VendorContext
    _run_ctx: ToolRunContext
    _session_id: Optional[str]
    _message_id: Optional[str]

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
        with SyncSessionLocal() as session:
            m = MembershipsRepo(session).get_membership(
                vendor_id=self._ctx.vendor_id, user_id=user_id, game_slug=game_slug
            )
            if m is None:
                return json.dumps(
                    {"error": f"No membership for user '{user_id}' on '{game_slug}'"}
                )
            current = m.get("trial_ends_at")
            new_trial_ends = (
                _parse_dt(current) + timedelta(days=int(extra_days))
                if current
                else _utcnow() + timedelta(days=int(extra_days))
            )
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
            proposal = _proposal_payload(
                ctx=self._ctx,
                action_type="extend_trial",
                payload=payload,
                preview=preview,
                run_ctx=self._run_ctx,
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
            session.commit()
            return self._emit(proposal, preview)


# ── update_membership_dates ────────────────────────────────────────────────────

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
        with SyncSessionLocal() as session:
            m = MembershipsRepo(session).get_membership(
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
            proposal = _proposal_payload(
                ctx=self._ctx,
                action_type="update_membership_dates",
                payload=payload,
                preview=preview,
                run_ctx=self._run_ctx,
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
                    metadata_json={"action_type": "update_membership_dates", "payload": payload},
                    created_at=_utcnow(),
                )
            )
            session.commit()
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
        new_plan = (new_plan or "").strip().lower()
        if new_plan not in ("free", "trial", "basic", "pro"):
            return json.dumps(
                {"error": "new_plan must be one of free|trial|basic|pro"}
            )
        with SyncSessionLocal() as session:
            m = MembershipsRepo(session).get_membership(
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
            proposal = _proposal_payload(
                ctx=self._ctx,
                action_type="change_plan",
                payload=payload,
                preview=preview,
                run_ctx=self._run_ctx,
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
            session.commit()
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
        with SyncSessionLocal() as session:
            u = UsersRepo(session).get_user(
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
            proposal = _proposal_payload(
                ctx=self._ctx,
                action_type="suspend_user",
                payload=payload,
                preview=preview,
                run_ctx=self._run_ctx,
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
            session.commit()
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
) -> list[BaseTool]:
    """Build propose_* tools closed over the authenticated vendor context."""
    tools: list[BaseTool] = []
    for cls in _WRITE_TOOL_CLASSES:
        instance = cls()
        instance._ctx = ctx
        instance._run_ctx = run_ctx
        instance._session_id = session_id
        instance._message_id = message_id
        tools.append(instance)
    return tools


def invoke_propose_tool_direct(
    action: str,
    args: dict[str, Any],
    ctx: VendorContext,
    run_ctx: ToolRunContext | None = None,
    *,
    session_id: str | None = None,
    message_id: str | None = None,
) -> str:
    """Call a propose_* tool by name without the agent (tests / deterministic path)."""
    run_ctx = run_ctx or ToolRunContext()
    tools = {
        t.name: t
        for t in build_write_tools(
            ctx, run_ctx, session_id=session_id, message_id=message_id
        )
    }
    if action not in tools:
        raise KeyError(f"Unknown propose tool: {action}")
    tool_obj = tools[action]
    return tool_obj.run(**args)


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        from datetime import datetime as _dt

        return _dt.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
