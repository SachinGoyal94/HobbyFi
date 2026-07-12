"""Approval service — the only place writes are executed.

Read path (Phase 1) is read-only. For writes, the agent creates a *pending*
``ActionProposal`` via a propose_* tool. This service owns the approve →
execute transition: it re-validates, executes idempotently, and records an
audit event. The LLM never reaches this code — only an authenticated vendor
user calling the decide endpoint can trigger execution (plan §12).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ActionProposal, AppUser, AuditEvent, Membership
from app.domain.schemas import ProposalDecision, VendorContext

_STATUS_TERMINAL = {"executed", "failed", "rejected", "expired", "cancelled"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def get_proposal(
    db: AsyncSession, *, proposal_id: str, vendor_id: str
) -> ActionProposal | None:
    return await db.scalar(
        select(ActionProposal).where(
            ActionProposal.id == proposal_id,
            ActionProposal.vendor_id == vendor_id,
        )
    )


async def list_proposals(
    db: AsyncSession, *, vendor_id: str, status: str | None = None
) -> list[ActionProposal]:
    stmt = select(ActionProposal).where(ActionProposal.vendor_id == vendor_id)
    if status:
        stmt = stmt.where(ActionProposal.status == status)
    stmt = stmt.order_by(ActionProposal.created_at.desc())
    return list((await db.scalars(stmt)).all())


def _is_expired(proposal: ActionProposal, now: datetime | None = None) -> bool:
    now = now or _utcnow()
    exp = proposal.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < now


async def decide_proposal(
    db: AsyncSession,
    *,
    proposal_id: str,
    ctx: VendorContext,
    decision: ProposalDecision,
    reason: str | None = None,
) -> ActionProposal:
    """Approve or reject a pending proposal.

    On approve, re-validates and executes idempotently. Records audit events.
    Raises ValueError with a message suitable for an HTTP error if the
    proposal is not actionable (expired / already decided / not found).
    """
    proposal = await get_proposal(db, proposal_id=proposal_id, vendor_id=ctx.vendor_id)
    if proposal is None:
        raise _ProposalError("Proposal not found", status_code=404)

    now = _utcnow()

    if proposal.status != "pending":
        raise _ProposalError(
            f"Proposal is '{proposal.status}', not pending. Cannot decide.",
            status_code=409,
        )

    if _is_expired(proposal, now):
        proposal.status = "expired"
        proposal.decided_by = ctx.vendor_user_id
        proposal.decided_at = now
        await db.flush()
        await _audit(
            db,
            ctx,
            "proposal.expired",
            proposal,
            {"auto": True},
        )
        raise _ProposalError("Proposal has expired.", status_code=409)

    proposal.decided_by = ctx.vendor_user_id
    proposal.decided_at = now

    if decision == "reject":
        proposal.status = "rejected"
        await db.flush()
        await _audit(
            db,
            ctx,
            "proposal.reject",
            proposal,
            {"reason": reason},
        )
        return proposal

    # approve → execute
    proposal.status = "approved"
    await db.flush()
    await _audit(db, ctx, "proposal.approve", proposal, {"reason": reason})

    execution_result = await _execute(db, proposal=proposal, ctx=ctx, now=now)

    if execution_result.get("ok"):
        proposal.status = "executed"
        proposal.execution_result = execution_result
    else:
        proposal.status = "failed"
        proposal.execution_result = execution_result

    await db.flush()
    await _audit(
        db,
        ctx,
        f"proposal.{proposal.status}",
        proposal,
        {"execution_result": execution_result},
    )
    return proposal


async def _execute(
    db: AsyncSession, *, proposal: ActionProposal, ctx: VendorContext, now: datetime
) -> dict:
    """Idempotent execution of a proposal's payload.

    Guards against double-execution via idempotency_key and re-validates the
    target still exists and is in the expected (tenant-scoped) state.
    """
    action = proposal.action_type
    payload = proposal.payload or {}

    # Idempotency: if a prior execution succeeded, do not repeat.
    if proposal.execution_result and proposal.execution_result.get("ok"):
        return {"ok": True, "idempotent": True, **(proposal.execution_result or {})}

    try:
        if action == "extend_trial":
            return await _exec_extend_trial(db, proposal, ctx, now)
        if action == "update_membership_dates":
            return await _exec_update_dates(db, proposal, ctx, now)
        if action == "change_plan":
            return await _exec_change_plan(db, proposal, ctx, now)
        if action == "suspend_user":
            return await _exec_suspend_user(db, proposal, ctx, now)
        return {"ok": False, "error": f"Unknown action_type: {action}"}
    except _ExecutionError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": f"execution error: {exc}"}


async def _resolve_membership(
    db: AsyncSession, *, ctx: VendorContext, user_id: str, game_slug: str
) -> Membership:
    """Re-validate target membership in the vendor scope (race protection)."""
    from app.domain.models import Game

    game = await db.scalar(
        select(Game).where(Game.vendor_id == ctx.vendor_id, Game.slug == game_slug)
    )
    if game is None:
        raise _ExecutionError(f"Game '{game_slug}' not found for this vendor")
    m = await db.scalar(
        select(Membership).where(
            Membership.vendor_id == ctx.vendor_id,
            Membership.user_id == user_id,
            Membership.game_id == game.id,
        )
    )
    if m is None:
        raise _ExecutionError(
            f"No membership for user '{user_id}' on '{game_slug}' (may have been removed)"
        )
    return m


async def _exec_extend_trial(
    db: AsyncSession, proposal: ActionProposal, ctx: VendorContext, now: datetime
) -> dict:
    payload = proposal.payload
    m = await _resolve_membership(
        db,
        ctx=ctx,
        user_id=payload["user_id"],
        game_slug=payload["game_slug"],
    )
    new_ends = _parse_dt(payload["new_trial_ends_at"])
    if new_ends is None:
        raise _ExecutionError("Invalid new_trial_ends_at in payload")
    m.trial_ends_at = new_ends
    await db.flush()
    return {
        "ok": True,
        "action": "extend_trial",
        "user_id": payload["user_id"],
        "game_slug": payload["game_slug"],
        "new_trial_ends_at": new_ends.isoformat(),
    }


async def _exec_update_dates(
    db: AsyncSession, proposal: ActionProposal, ctx: VendorContext, now: datetime
) -> dict:
    payload = proposal.payload
    m = await _resolve_membership(
        db,
        ctx=ctx,
        user_id=payload["user_id"],
        game_slug=payload["game_slug"],
    )
    if payload.get("starts_at"):
        starts = _parse_dt(payload["starts_at"])
        if starts:
            m.starts_at = starts
    if payload.get("ends_at"):
        ends = _parse_dt(payload["ends_at"])
        if ends:
            m.ends_at = ends
    await db.flush()
    return {
        "ok": True,
        "action": "update_membership_dates",
        "user_id": payload["user_id"],
        "game_slug": payload["game_slug"],
        "starts_at": m.starts_at.isoformat() if m.starts_at else None,
        "ends_at": m.ends_at.isoformat() if m.ends_at else None,
    }


async def _exec_change_plan(
    db: AsyncSession, proposal: ActionProposal, ctx: VendorContext, now: datetime
) -> dict:
    payload = proposal.payload
    m = await _resolve_membership(
        db,
        ctx=ctx,
        user_id=payload["user_id"],
        game_slug=payload["game_slug"],
    )
    if payload["new_plan"] not in ("free", "trial", "basic", "pro"):
        raise _ExecutionError(f"Invalid plan: {payload['new_plan']}")
    m.plan = payload["new_plan"]
    await db.flush()
    return {
        "ok": True,
        "action": "change_plan",
        "user_id": payload["user_id"],
        "game_slug": payload["game_slug"],
        "new_plan": payload["new_plan"],
    }


async def _exec_suspend_user(
    db: AsyncSession, proposal: ActionProposal, ctx: VendorContext, now: datetime
) -> dict:
    payload = proposal.payload
    user = await db.scalar(
        select(AppUser).where(
            AppUser.vendor_id == ctx.vendor_id, AppUser.id == payload["user_id"]
        )
    )
    if user is None:
        raise _ExecutionError(f"User '{payload['user_id']}' not found")
    user.status = "suspended"
    await db.flush()
    return {
        "ok": True,
        "action": "suspend_user",
        "user_id": payload["user_id"],
        "status": "suspended",
    }


async def expire_overdue_proposals(
    db: AsyncSession, *, vendor_id: str | None = None, now: datetime | None = None
) -> int:
    """Mark pending proposals past their expires_at as 'expired'.

    Returns number expired. Safe to call from a background task.
    """
    now = now or _utcnow()
    stmt = select(ActionProposal).where(
        ActionProposal.status == "pending",
        ActionProposal.expires_at < now,
    )
    if vendor_id:
        stmt = stmt.where(ActionProposal.vendor_id == vendor_id)
    proposals: Sequence[ActionProposal] = (await db.scalars(stmt)).all()
    count = 0
    for p in proposals:
        p.status = "expired"
        p.decided_at = now
        count += 1
    await db.flush()
    return count


async def _audit(
    db: AsyncSession,
    ctx: VendorContext,
    event_type: str,
    proposal: ActionProposal,
    extra: dict,
) -> None:
    db.add(
        AuditEvent(
            id=_new_id("ae"),
            vendor_id=ctx.vendor_id,
            actor_id=ctx.vendor_user_id,
            event_type=event_type,
            entity_type="action_proposal",
            entity_id=proposal.id,
            metadata_json={
                "action_type": proposal.action_type,
                "decision": extra,
            },
            created_at=_utcnow(),
        )
    )
    await db.flush()


class _ProposalError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class _ExecutionError(Exception):
    pass


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        from datetime import datetime as _dt

        return _dt.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
