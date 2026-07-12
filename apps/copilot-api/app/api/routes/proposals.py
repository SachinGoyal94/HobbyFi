"""Approval routes — list/detail/decide proposals + vendor-scoped audit.

Phase 2: writes are propose → approve → execute. The decide endpoint is the
ONLY place execution happens, and it requires an authenticated vendor user
(never the LLM). Roles are gated per plan open-question #1: owners/admins/
support can approve (not viewers).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limiter import rate_limit_dependency
from app.db.session import get_db
from app.deps import get_vendor_context, require_role
from app.domain.schemas import (
    ActionProposalResponse,
    ProposalDecisionRequest,
    ProposalListResponse,
    VendorContext,
)
from app.services import approval_service

router = APIRouter()

# Roles allowed to approve/reject (plan open-question #1 default).
_APPROVER_ROLES = ("owner", "admin", "support")


@router.get("", response_model=ProposalListResponse)
async def list_proposals(
    status: str | None = None,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_dependency),
) -> ProposalListResponse:
    """List this vendor's proposals, optionally filtered by status."""
    proposals = await approval_service.list_proposals(
        db, vendor_id=ctx.vendor_id, status=status
    )
    return ProposalListResponse(
        proposals=[ActionProposalResponse.model_validate(p) for p in proposals],
        count=len(proposals),
    )


@router.get("/{proposal_id}", response_model=ActionProposalResponse)
async def get_proposal(
    proposal_id: str,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_dependency),
) -> ActionProposalResponse:
    """Get a single proposal + its preview (vendor-scoped)."""
    proposal = await approval_service.get_proposal(
        db, proposal_id=proposal_id, vendor_id=ctx.vendor_id
    )
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    return ActionProposalResponse.model_validate(proposal)


@router.post("/{proposal_id}/decide", response_model=ActionProposalResponse)
async def decide_proposal(
    proposal_id: str,
    body: ProposalDecisionRequest,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_dependency),
    _role: None = Depends(require_role("owner", "admin", "support")),
) -> ActionProposalResponse:
    """Approve or reject a pending proposal.

    Execution happens here on approve — server-side, idempotent, re-validated.
    The LLM cannot call this endpoint (it is an authenticated human action).
    """
    try:
        proposal = await approval_service.decide_proposal(
            db,
            proposal_id=proposal_id,
            ctx=ctx,
            decision=body.decision,
            reason=body.reason,
        )
    except approval_service._ProposalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return ActionProposalResponse.model_validate(proposal)
