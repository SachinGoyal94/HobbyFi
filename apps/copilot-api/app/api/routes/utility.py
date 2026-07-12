"""Dev-only admin and debug routes + vendor-scoped audit (no /v1/copilot prefix)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_vendor_context, require_role
from app.domain.models import AuditEvent
from app.domain.schemas import (
    AuditEventResponse,
    AuditListResponse,
    SeedSummary,
    VendorContext,
)
from app.domain.seed import seed_mock_data

router = APIRouter()


@router.post("/v1/admin/seed", response_model=SeedSummary, include_in_schema=False)
async def reseed(
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-run seed (idempotent). Dev-only; not in OpenAPI schema."""
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(status_code=403)
    counts = await seed_mock_data(db)
    await db.commit()
    return counts


@router.get("/v1/copilot/me", response_model=VendorContext)
async def whoami(ctx: VendorContext = Depends(get_vendor_context)):
    """Echo the authenticated vendor context for debugging."""
    return ctx


@router.get("/v1/copilot/audit", response_model=AuditListResponse)
async def list_audit(
    limit: int = 100,
    ctx: VendorContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> AuditListResponse:
    """Vendor-scoped audit trail (owner/admin only)."""
    limit = max(1, min(limit, 500))
    events = (
        await db.scalars(
            select(AuditEvent)
            .where(AuditEvent.vendor_id == ctx.vendor_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
    ).all()
    return AuditListResponse(
        events=[AuditEventResponse.model_validate(e) for e in events],
        count=len(events),
    )