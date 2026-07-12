"""Seed mock domain data for local development, tests, and demos.

This seed is designed to be FULLY TEST-COMPATIBLE while also providing
richer demo data for additional scenarios.

All test-expected IDs, counts, and values are preserved exactly.
"""

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

# ════════════════════════════════════════════════════════════════════════════
# TEST-COMPATIBLE CONSTANTS — MUST MATCH EXISTING TESTS EXACTLY
# ════════════════════════════════════════════════════════════════════════════

# Vendor Acme Sports (primary demo vendor)
VENDOR_ACME = "v_acme"
VENDOR_ACME_NAME = "Acme Sports"
VENDOR_ACME_TZ = "Asia/Kolkata"

ACME_ADMIN = "vu_admin"
ACME_SUPPORT = "vu_support"
ACME_VIEWER = "vu_viewer"

GAME_BADMINTON = "g_badminton"
GAME_CRICKET = "g_cricket"

# App users — TEST COMPATIBLE
USER_ALICE = "u_alice"
USER_BOB = "u_bob"
USER_CAROL = "u_carol"
USER_DAVE = "u_dave"

# Membership IDs — TEST COMPATIBLE
M_ALICE_BADMINTON = "m_alice_badminton"
M_CAROL_BADMINTON = "m_carol_badminton"
M_BOB_CRICKET = "m_bob_cricket"
M_DAVE_CRICKET = "m_dave_cricket"

# ════════════════════════════════════════════════════════════════════════════
# Vendor Beta Games Co (secondary vendor for tenancy demo) — TEST COMPATIBLE
# ════════════════════════════════════════════════════════════════════════════

VENDOR_BETA = "v_beta"
VENDOR_BETA_NAME = "Beta Games Co"
VENDOR_BETA_TZ = "UTC"

BETA_ADMIN = "vu_beta_admin"
BETA_SUPPORT = "vu_beta_support"
BETA_VIEWER = "vu_beta_viewer"

GAME_TENNIS = "g_tennis"
GAME_SQUASH = "g_squash"
GAME_PICKLEBALL = "g_pickleball"

BETA_USER_EVE = "u_beta_eve"
M_EVE_TENNIS = "m_eve_tennis"

# ════════════════════════════════════════════════════════════════════════════
# ADDITIONAL DEMO DATA CONSTANTS (not tested, safe to add)
# ════════════════════════════════════════════════════════════════════════════

USER_EVE = "u_eve"
USER_FRANK = "u_frank"
USER_GRACE = "u_grace"
USER_HEIDI = "u_heidi"
USER_IVAN = "u_ivan"
USER_JUDY = "u_judy"
USER_KARL = "u_karl"
USER_LENA = "u_lena"

# ════════════════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════════════
    # VENDORS & VENDOR USERS
    # ═══════════════════════════════════════════════════════════════════════════

    session.add_all([
        # Acme Sports (primary demo vendor) — TEST COMPATIBLE
        Vendor(id=VENDOR_ACME, name=VENDOR_ACME_NAME, timezone=VENDOR_ACME_TZ, created_at=now - timedelta(days=180)),
        VendorUser(id=ACME_ADMIN, vendor_id=VENDOR_ACME, email="admin@acme.example", role="admin", created_at=now - timedelta(days=180)),
        VendorUser(id=ACME_SUPPORT, vendor_id=VENDOR_ACME, email="support@acme.example", role="support", created_at=now - timedelta(days=120)),
        VendorUser(id=ACME_VIEWER, vendor_id=VENDOR_ACME, email="viewer@acme.example", role="viewer", created_at=now - timedelta(days=60)),

        # Beta Games Co (secondary vendor for tenancy tests) — TEST COMPATIBLE
        Vendor(id=VENDOR_BETA, name=VENDOR_BETA_NAME, timezone=VENDOR_BETA_TZ, created_at=now - timedelta(days=90)),
        VendorUser(id=BETA_ADMIN, vendor_id=VENDOR_BETA, email="admin@beta.example", role="admin", created_at=now - timedelta(days=90)),
        VendorUser(id=BETA_SUPPORT, vendor_id=VENDOR_BETA, email="support@beta.example", role="support", created_at=now - timedelta(days=60)),
        VendorUser(id=BETA_VIEWER, vendor_id=VENDOR_BETA, email="viewer@beta.example", role="viewer", created_at=now - timedelta(days=30)),
    ])

    # ═══════════════════════════════════════════════════════════════════════════
    # GAMES — TEST COMPATIBLE: Acme has exactly 2 (badminton, cricket)
    # ═══════════════════════════════════════════════════════════════════════════

    session.add_all([
        # Acme games — TEST COMPATIBLE: exactly 2
        Game(id=GAME_BADMINTON, vendor_id=VENDOR_ACME, slug="badminton", name="Badminton"),
        Game(id=GAME_CRICKET, vendor_id=VENDOR_ACME, slug="cricket", name="Cricket"),

        # Beta games — TEST COMPATIBLE: exactly 1 (tennis)
        Game(id=GAME_TENNIS, vendor_id=VENDOR_BETA, slug="tennis", name="Tennis"),
    ])

    # ═══════════════════════════════════════════════════════════════════════════
    # APP USERS (end users)
    # ═══════════════════════════════════════════════════════════════════════════

    session.add_all([
        # TEST COMPATIBLE users
        AppUser(id=USER_ALICE, vendor_id=VENDOR_ACME, email="alice@example.com", display_name="Alice", status="active", created_at=now - timedelta(days=20)),
        AppUser(id=USER_BOB, vendor_id=VENDOR_ACME, email="bob@example.com", display_name="Bob", status="active", created_at=now - timedelta(days=40)),
        AppUser(id=USER_CAROL, vendor_id=VENDOR_ACME, email="carol@example.com", display_name="Carol", status="active", created_at=now - timedelta(days=5)),
        AppUser(id=USER_DAVE, vendor_id=VENDOR_ACME, email="dave@example.com", display_name="Dave", status="suspended", created_at=now - timedelta(days=90)),

        # Beta user — TEST COMPATIBLE
        AppUser(id=BETA_USER_EVE, vendor_id=VENDOR_BETA, email="eve@beta.example", display_name="Eve", status="active", created_at=now),

        # Additional demo users (not tested)
        AppUser(id=USER_FRANK, vendor_id=VENDOR_ACME, email="frank@example.com", display_name="Frank", status="active", created_at=now - timedelta(days=60)),
        AppUser(id=USER_GRACE, vendor_id=VENDOR_ACME, email="grace@example.com", display_name="Grace", status="active", created_at=now - timedelta(days=10)),
        AppUser(id=USER_HEIDI, vendor_id=VENDOR_ACME, email="heidi@example.com", display_name="Heidi", status="churned", created_at=now - timedelta(days=120)),
        AppUser(id=USER_IVAN, vendor_id=VENDOR_ACME, email="ivan@example.com", display_name="Ivan", status="active", created_at=now - timedelta(days=30)),
        AppUser(id=USER_JUDY, vendor_id=VENDOR_ACME, email="judy@example.com", display_name="Judy", status="active", created_at=now - timedelta(days=45)),
        AppUser(id=USER_KARL, vendor_id=VENDOR_ACME, email="karl@example.com", display_name="Karl", status="active", created_at=now - timedelta(days=8)),
        AppUser(id=USER_LENA, vendor_id=VENDOR_ACME, email="lena@example.com", display_name="Lena", status="active", created_at=now - timedelta(days=2)),
    ])

    # ═══════════════════════════════════════════════════════════════════════════
    # MEMBERSHIPS
    # ═══════════════════════════════════════════════════════════════════════════

    memberships = [
        # TEST COMPATIBLE memberships
        Membership(
            id=M_ALICE_BADMINTON, vendor_id=VENDOR_ACME, user_id=USER_ALICE, game_id=GAME_BADMINTON,
            plan="trial", starts_at=now - timedelta(days=3), ends_at=None,
            trial_ends_at=now + timedelta(days=4), status="active",
        ),
        Membership(
            id=M_CAROL_BADMINTON, vendor_id=VENDOR_ACME, user_id=USER_CAROL, game_id=GAME_BADMINTON,
            plan="trial", starts_at=now - timedelta(days=1), ends_at=None,
            trial_ends_at=now + timedelta(days=13), status="active",
        ),
        Membership(
            id=M_BOB_CRICKET, vendor_id=VENDOR_ACME, user_id=USER_BOB, game_id=GAME_CRICKET,
            plan="pro", starts_at=now - timedelta(days=30), ends_at=now + timedelta(days=335),
            trial_ends_at=None, status="active",
        ),
        Membership(
            id=M_DAVE_CRICKET, vendor_id=VENDOR_ACME, user_id=USER_DAVE, game_id=GAME_CRICKET,
            plan="basic", starts_at=now - timedelta(days=60), ends_at=now - timedelta(days=5),
            trial_ends_at=None, status="expired",
        ),

        # Beta membership — TEST COMPATIBLE
        Membership(
            id=M_EVE_TENNIS, vendor_id=VENDOR_BETA, user_id=BETA_USER_EVE, game_id=GAME_TENNIS,
            plan="trial", starts_at=now, ends_at=None, trial_ends_at=now + timedelta(days=7), status="active",
        ),

        # ═══════════════════════════════════════════════════════════════════════════
        # ADDITIONAL DEMO MEMBERSHIPS (not tested) — ONLY BADMINTON/CRICKET GAMES
        # ═══════════════════════════════════════════════════════════════════════════════

        # Alice — also plays cricket (pro)
        Membership(
            id="m_alice_cricket", vendor_id=VENDOR_ACME, user_id=USER_ALICE, game_id=GAME_CRICKET,
            plan="pro", starts_at=now - timedelta(days=10), ends_at=now + timedelta(days=355),
            trial_ends_at=None, status="active",
        ),
        # Bob — also plays badminton (basic)
        Membership(
            id="m_bob_badminton", vendor_id=VENDOR_ACME, user_id=USER_BOB, game_id=GAME_BADMINTON,
            plan="basic", starts_at=now - timedelta(days=20), ends_at=now + timedelta(days=345),
            trial_ends_at=None, status="active",
        ),
        # Carol — cricket trial
        Membership(
            id="m_carol_cricket", vendor_id=VENDOR_ACME, user_id=USER_CAROL, game_id=GAME_CRICKET,
            plan="trial", starts_at=now - timedelta(days=3), ends_at=None,
            trial_ends_at=now + timedelta(days=10), status="active",
        ),
        # Frank — basic cricket
        Membership(
            id="m_frank_cricket", vendor_id=VENDOR_ACME, user_id=USER_FRANK, game_id=GAME_CRICKET,
            plan="basic", starts_at=now - timedelta(days=45), ends_at=now + timedelta(days=320),
            trial_ends_at=None, status="active",
        ),
        # Grace — pro cricket
        Membership(
            id="m_grace_cricket", vendor_id=VENDOR_ACME, user_id=USER_GRACE, game_id=GAME_CRICKET,
            plan="pro", starts_at=now - timedelta(days=30), ends_at=now + timedelta(days=335),
            trial_ends_at=None, status="active",
        ),
        # Heidi — expired basic badminton (churned)
        Membership(
            id="m_heidi_badminton", vendor_id=VENDOR_ACME, user_id=USER_HEIDI, game_id=GAME_BADMINTON,
            plan="basic", starts_at=now - timedelta(days=100), ends_at=now - timedelta(days=10),
            trial_ends_at=None, status="expired",
        ),
        # Ivan — trial cricket
        Membership(
            id="m_ivan_cricket", vendor_id=VENDOR_ACME, user_id=USER_IVAN, game_id=GAME_CRICKET,
            plan="trial", starts_at=now - timedelta(days=2), ends_at=None,
            trial_ends_at=now + timedelta(days=11), status="active",
        ),
        # Judy — trial cricket
        Membership(
            id="m_judy_cricket", vendor_id=VENDOR_ACME, user_id=USER_JUDY, game_id=GAME_CRICKET,
            plan="trial", starts_at=now - timedelta(days=5), ends_at=None,
            trial_ends_at=now + timedelta(days=9), status="active",
        ),
        # Karl — basic cricket
        Membership(
            id="m_karl_cricket", vendor_id=VENDOR_ACME, user_id=USER_KARL, game_id=GAME_CRICKET,
            plan="basic", starts_at=now - timedelta(days=15), ends_at=now + timedelta(days=350),
            trial_ends_at=None, status="active",
        ),
        # Lena — trial cricket (new user, 8 days ago)
        Membership(
            id="m_lena_cricket", vendor_id=VENDOR_ACME, user_id=USER_LENA, game_id=GAME_CRICKET,
            plan="trial", starts_at=now - timedelta(days=8), ends_at=None,
            trial_ends_at=now + timedelta(days=6), status="active",
        ),
    ]

    session.add_all(memberships)

    # ═══════════════════════════════════════════════════════════════════════════
    # REVENUE DAILY — MUST MATCH TEST EXPECTATIONS EXACTLY
    # ═══════════════════════════════════════════════════════════════════════════

    revenue_rows = []

    # Acme Sports — TODAY (timezone Asia/Kolkata) — TEST EXPECTS: net_cents = 128_500
    revenue_rows.append(RevenueDaily(
        id="rev_acme_all_today", vendor_id=VENDOR_ACME, game_id=None,
        day=today, currency="USD", gross_cents=132_000, refunds_cents=3_500, net_cents=128_500,
    ))
    # Acme — badminton today
    revenue_rows.append(RevenueDaily(
        id="rev_acme_badminton_today", vendor_id=VENDOR_ACME, game_id=GAME_BADMINTON,
        day=today, currency="USD", gross_cents=45_000, refunds_cents=1_000, net_cents=44_000,
    ))
    # Acme — cricket today
    revenue_rows.append(RevenueDaily(
        id="rev_acme_cricket_today", vendor_id=VENDOR_ACME, game_id=GAME_CRICKET,
        day=today, currency="USD", gross_cents=87_000, refunds_cents=2_500, net_cents=84_500,
    ))

    # Acme — YESTERDAY (not tested but kept for demo)
    revenue_rows.append(RevenueDaily(
        id="rev_acme_all_yesterday", vendor_id=VENDOR_ACME, game_id=None,
        day=yesterday, currency="USD", gross_cents=110_000, refunds_cents=2_000, net_cents=108_000,
    ))

    # Beta Games Co — TODAY — TEST EXPECTS: net_cents = 9_900
    revenue_rows.append(RevenueDaily(
        id="rev_beta_today", vendor_id=VENDOR_BETA, game_id=None,
        day=today, currency="USD", gross_cents=9_900, refunds_cents=0, net_cents=9_900,
    ))

    session.add_all(revenue_rows)

    await session.flush()
    return await _counts(session)


async def _counts(session: AsyncSession) -> dict[str, int]:
    return {
        "vendors": int(await session.scalar(select(func.count()).select_from(Vendor)) or 0),
        "vendor_users": int(await session.scalar(select(func.count()).select_from(VendorUser)) or 0),
        "games": int(await session.scalar(select(func.count()).select_from(Game)) or 0),
        "app_users": int(await session.scalar(select(func.count()).select_from(AppUser)) or 0),
        "memberships": int(await session.scalar(select(func.count()).select_from(Membership)) or 0),
        "revenue_rows": int(await session.scalar(select(func.count()).select_from(RevenueDaily)) or 0),
    }