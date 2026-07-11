"""Dev-only admin and debug routes (not under /v1/copilot prefix)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_vendor_context
from app.domain.schemas import SeedSummary, VendorContext
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