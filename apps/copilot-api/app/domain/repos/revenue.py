from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.domain.models import Game, RevenueDaily, AppUser, Membership


class RevenueRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_revenue(
        self,
        *,
        vendor_id: str,
        day: date | None = None,
        game_slug: str | None = None,
        timezone_name: str = "UTC",
    ) -> dict:
        if day is None:
            try:
                tz = ZoneInfo(timezone_name)
            except Exception:
                tz = ZoneInfo("UTC")
            from datetime import datetime, timezone

            day = datetime.now(timezone.utc).astimezone(tz).date()

        game_id: str | None = None
        game_name: str | None = None
        if game_slug:
            game = await self._session.scalar(
                select(Game).where(Game.vendor_id == vendor_id, Game.slug == game_slug)
            )
            if game is None:
                return {
                    "day": day.isoformat(),
                    "game_slug": game_slug,
                    "found": False,
                    "error": f"Game '{game_slug}' not found for this vendor",
                    "rows": [],
                }
            game_id = game.id
            game_name = game.name

        stmt = select(RevenueDaily).where(
            RevenueDaily.vendor_id == vendor_id,
            RevenueDaily.day == day,
        )
        if game_id is not None:
            stmt = stmt.where(RevenueDaily.game_id == game_id)
        else:
            # Prefer all-games rollup (game_id IS NULL); fall back to per-game rows
            rollup = await self._session.scalar(
                select(RevenueDaily).where(
                    RevenueDaily.vendor_id == vendor_id,
                    RevenueDaily.day == day,
                    RevenueDaily.game_id.is_(None),
                )
            )
            if rollup is not None:
                return {
                    "day": day.isoformat(),
                    "game_slug": None,
                    "game_name": None,
                    "found": True,
                    "currency": rollup.currency,
                    "gross_cents": rollup.gross_cents,
                    "refunds_cents": rollup.refunds_cents,
                    "net_cents": rollup.net_cents,
                    "gross": _cents_to_dollars(rollup.gross_cents),
                    "refunds": _cents_to_dollars(rollup.refunds_cents),
                    "net": _cents_to_dollars(rollup.net_cents),
                    "rows": [_row_dict(rollup)],
                }

        rows = (await self._session.scalars(stmt)).all()
        if not rows:
            return {
                "day": day.isoformat(),
                "game_slug": game_slug,
                "game_name": game_name,
                "found": False,
                "rows": [],
                "net_cents": 0,
                "gross_cents": 0,
                "refunds_cents": 0,
                "net": "0.00",
                "gross": "0.00",
                "refunds": "0.00",
            }

        gross = sum(r.gross_cents for r in rows)
        refunds = sum(r.refunds_cents for r in rows)
        net = sum(r.net_cents for r in rows)
        currency = rows[0].currency
        return {
            "day": day.isoformat(),
            "game_slug": game_slug,
            "game_name": game_name,
            "found": True,
            "currency": currency,
            "gross_cents": gross,
            "refunds_cents": refunds,
            "net_cents": net,
            "gross": _cents_to_dollars(gross),
            "refunds": _cents_to_dollars(refunds),
            "net": _cents_to_dollars(net),
            "rows": [_row_dict(r) for r in rows],
        }

    async def vendor_summary(self, *, vendor_id: str, day: date | None = None, timezone_name: str = "UTC") -> dict:
        if day is None:
            try:
                tz = ZoneInfo(timezone_name)
            except Exception:
                tz = ZoneInfo("UTC")
            from datetime import datetime, timezone

            day = datetime.now(timezone.utc).astimezone(tz).date()

        active_users = int(
            (await self._session.scalar(
                select(func.count())
                .select_from(AppUser)
                .where(AppUser.vendor_id == vendor_id, AppUser.status == "active")
            ))
            or 0
        )
        active_trials = int(
            (await self._session.scalar(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.vendor_id == vendor_id,
                    Membership.plan == "trial",
                    Membership.status == "active",
                )
            ))
            or 0
        )
        game_count = int(
            (await self._session.scalar(
                select(func.count()).select_from(Game).where(Game.vendor_id == vendor_id)
            ))
            or 0
        )
        rev = await self.get_revenue(vendor_id=vendor_id, day=day, timezone_name=timezone_name)
        return {
            "day": day.isoformat(),
            "active_users": active_users,
            "active_trials": active_trials,
            "game_count": game_count,
            "revenue": {
                "found": rev.get("found"),
                "currency": rev.get("currency", "USD"),
                "net": rev.get("net", "0.00"),
                "gross": rev.get("gross", "0.00"),
                "net_cents": rev.get("net_cents", 0),
            },
        }


def _cents_to_dollars(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _row_dict(r: RevenueDaily) -> dict:
    return {
        "id": r.id,
        "game_id": r.game_id,
        "day": r.day.isoformat(),
        "currency": r.currency,
        "gross_cents": r.gross_cents,
        "refunds_cents": r.refunds_cents,
        "net_cents": r.net_cents,
        "net": _cents_to_dollars(r.net_cents),
    }
