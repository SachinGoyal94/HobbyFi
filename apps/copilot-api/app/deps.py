"""FastAPI dependencies for DI, auth context, and service lookup.

Phase 0 uses a stub auth header. Phase 4 swaps this for real JWT / SSO.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.models import Vendor, VendorUser
from app.domain.schemas import Role, VendorContext

# ── Auth header stubs (Phase 0) ──────────────────────────────────────────────

HEADER_VENDOR_ID = "x-vendor-id"
HEADER_VENDOR_USER_ID = "x-vendor-user-id"
HEADER_VENDOR_ROLE = "x-vendor-role"


async def get_vendor_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_vendor_id: str | None = Header(None, alias="x-vendor-id"),
    x_vendor_user_id: str | None = Header(None, alias="x-vendor-user-id"),
    x_vendor_role: str | None = Header(None, alias="x-vendor-role"),
) -> VendorContext:
    """Build VendorContext from stub headers; validates against DB.

    In production (Phase 4), this is replaced by JWT / SSO validation with the
    same `VendorContext` return shape — all downstream code stays unchanged.
    """
    if not x_vendor_id or not x_vendor_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-vendor-id or x-vendor-user-id header",
        )

    role = x_vendor_role or "viewer"
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {role}. Must be one of {sorted(_VALID_ROLES)}",
        )

    # Validate vendor exists
    vendor = await db.scalar(select(Vendor).where(Vendor.id == x_vendor_id))
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Vendor '{x_vendor_id}' not found",
        )

    # Validate vendor user
    user = await db.scalar(
        select(VendorUser).where(
            VendorUser.id == x_vendor_user_id,
            VendorUser.vendor_id == x_vendor_id,
        )
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Vendor user '{x_vendor_user_id}' not found for vendor '{x_vendor_id}'",
        )

    # Ensure header role matches stored role (for stub integrity)
    if user.role != role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role mismatch: header says {role}, DB has {user.role}",
        )

    ctx = VendorContext(
        vendor_id=vendor.id,
        vendor_user_id=user.id,
        email=user.email,
        role=role,  # type: ignore[arg-type]
        timezone=vendor.timezone,
        vendor_name=vendor.name,
    )
    # Store in request.state for rate limiter and other middleware
    request.state.vendor_context = ctx
    return ctx


_VALID_ROLES: set[str] = {"owner", "admin", "support", "viewer"}


def require_role(*allowed: Role):
    """Dependency factory: gate an endpoint to specific roles."""

    async def _check(ctx: VendorContext = Depends(get_vendor_context)) -> VendorContext:
        if ctx.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{ctx.role}' not permitted. Required: {list(allowed)}",
            )
        return ctx

    return _check