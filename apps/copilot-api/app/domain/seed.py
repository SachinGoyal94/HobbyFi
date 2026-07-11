"""Seed mock domain data for local development and tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    AppUser,
    Game,
    Membership,
    RevenueDaily,
    Vendor,
    VendorUser,
)

VENDOR_ID = "v_acme"
VENDOR_USER_ADMIN = "vu_admin"
VENDOR_USER_SUPPORT = "vu_support"
VENDOR_USER_VIEWER = "vu_viewer"

GAME_BADMINTON = "g_badminton"
GAME_CRICKET = "g_cricket"


async def is_seeded(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count()).select_from(Vendor))
    return bool(count and count > 0)


async def seed_mock_data(session: AsyncSession) -> dict[str, int]:
    """Idempotent seed: no-op if vendors already exist."""
    if await is_seeded(session):
        return await _counts(session)

    now = datetime.now(timezone.utc)
    today = date.today()
    yesterday = today - timedelta(days=1)

    session.add(
        Vendor(
            id=VENDOR_ID,
            name="Acme Sports",
            timezone="Asia/Kolkata",
            created_at=now,
        )
    )

    session.add_all(
        [
            VendorUser(
                id=VENDOR_USER_ADMIN,
                vendor_id=VENDOR_ID,
                email="admin@acme.example",
                role="admin",
                created_at=now,
            ),
            VendorUser(
                id=VENDOR_USER_SUPPORT,
                vendor_id=VENDOR_ID,
                email="support@acme.example",
                role="support",
                created_at=now,
            ),
            VendorUser(
                id=VENDOR_USER_VIEWER,
                vendor_id=VENDOR_ID,
                email="viewer@acme.example",
                role="viewer",
                created_at=now,
            ),
            # Second vendor for tenancy tests later
            Vendor(
                id="v_beta",
                name="Beta Games Co",
                timezone="UTC",
                created_at=now,
            ),
            VendorUser(
                id="vu_beta_admin",
                vendor_id="v_beta",
                email="admin@beta.example",
                role="admin",
                created_at=now,
            ),
        ]
    )

    session.add_all(
        [
            Game(
                id=GAME_BADMINTON,
                vendor_id=VENDOR_ID,
                slug="badminton",
                name="Badminton",
            ),
            Game(
                id=GAME_CRICKET,
                vendor_id=VENDOR_ID,
                slug="cricket",
                name="Cricket",
            ),
            Game(
                id="g_beta_tennis",
                vendor_id="v_beta",
                slug="tennis",
                name="Tennis",
            ),
        ]
    )

    session.add_all(
        [
            AppUser(
                id="u_alice",
                vendor_id=VENDOR_ID,
                email="alice@example.com",
                display_name="Alice",
                status="active",
                created_at=now - timedelta(days=20),
            ),
            AppUser(
                id="u_bob",
                vendor_id=VENDOR_ID,
                email="bob@example.com",
                display_name="Bob",
                status="active",
                created_at=now - timedelta(days=40),
            ),
            AppUser(
                id="u_carol",
                vendor_id=VENDOR_ID,
                email="carol@example.com",
                display_name="Carol",
                status="active",
                created_at=now - timedelta(days=5),
            ),
            AppUser(
                id="u_dave",
                vendor_id=VENDOR_ID,
                email="dave@example.com",
                display_name="Dave",
                status="suspended",
                created_at=now - timedelta(days=90),
            ),
            AppUser(
                id="u_beta_eve",
                vendor_id="v_beta",
                email="eve@beta.example",
                display_name="Eve",
                status="active",
                created_at=now,
            ),
        ]
    )

    session.add_all(
        [
            Membership(
                id="m_alice_badminton",
                vendor_id=VENDOR_ID,
                user_id="u_alice",
                game_id=GAME_BADMINTON,
                plan="trial",
                starts_at=now - timedelta(days=3),
                ends_at=None,
                trial_ends_at=now + timedelta(days=4),
                status="active",
            ),
            Membership(
                id="m_carol_badminton",
                vendor_id=VENDOR_ID,
                user_id="u_carol",
                game_id=GAME_BADMINTON,
                plan="trial",
                starts_at=now - timedelta(days=1),
                ends_at=None,
                trial_ends_at=now + timedelta(days=13),
                status="active",
            ),
            Membership(
                id="m_bob_cricket",
                vendor_id=VENDOR_ID,
                user_id="u_bob",
                game_id=GAME_CRICKET,
                plan="pro",
                starts_at=now - timedelta(days=30),
                ends_at=now + timedelta(days=335),
                trial_ends_at=None,
                status="active",
            ),
            Membership(
                id="m_dave_cricket",
                vendor_id=VENDOR_ID,
                user_id="u_dave",
                game_id=GAME_CRICKET,
                plan="basic",
                starts_at=now - timedelta(days=60),
                ends_at=now - timedelta(days=5),
                trial_ends_at=None,
                status="expired",
            ),
            Membership(
                id="m_eve_tennis",
                vendor_id="v_beta",
                user_id="u_beta_eve",
                game_id="g_beta_tennis",
                plan="trial",
                starts_at=now,
                ends_at=None,
                trial_ends_at=now + timedelta(days=7),
                status="active",
            ),
        ]
    )

    session.add_all(
        [
            RevenueDaily(
                id="rev_acme_all_today",
                vendor_id=VENDOR_ID,
                game_id=None,
                day=today,
                currency="USD",
                gross_cents=132_000,
                refunds_cents=3_500,
                net_cents=128_500,
            ),
            RevenueDaily(
                id="rev_acme_badminton_today",
                vendor_id=VENDOR_ID,
                game_id=GAME_BADMINTON,
                day=today,
                currency="USD",
                gross_cents=45_000,
                refunds_cents=1_000,
                net_cents=44_000,
            ),
            RevenueDaily(
                id="rev_acme_cricket_today",
                vendor_id=VENDOR_ID,
                game_id=GAME_CRICKET,
                day=today,
                currency="USD",
                gross_cents=87_000,
                refunds_cents=2_500,
                net_cents=84_500,
            ),
            RevenueDaily(
                id="rev_acme_all_yesterday",
                vendor_id=VENDOR_ID,
                game_id=None,
                day=yesterday,
                currency="USD",
                gross_cents=110_000,
                refunds_cents=2_000,
                net_cents=108_000,
            ),
            RevenueDaily(
                id="rev_beta_today",
                vendor_id="v_beta",
                game_id=None,
                day=today,
                currency="USD",
                gross_cents=9_900,
                refunds_cents=0,
                net_cents=9_900,
            ),
        ]
    )

    await session.flush()
    return await _counts(session)


async def _counts(session: AsyncSession) -> dict[str, int]:
    return {
        "vendors": int(await session.scalar(select(func.count()).select_from(Vendor)) or 0),
        "vendor_users": int(
            await session.scalar(select(func.count()).select_from(VendorUser)) or 0
        ),
        "games": int(await session.scalar(select(func.count()).select_from(Game)) or 0),
        "app_users": int(await session.scalar(select(func.count()).select_from(AppUser)) or 0),
        "memberships": int(
            await session.scalar(select(func.count()).select_from(Membership)) or 0
        ),
        "revenue_rows": int(
            await session.scalar(select(func.count()).select_from(RevenueDaily)) or 0
        ),
    }
