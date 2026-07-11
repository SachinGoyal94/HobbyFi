from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.models import AppUser, Game, Membership


class MembershipsRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_trials(
        self,
        *,
        vendor_id: str,
        game_slug: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        limit = max(1, min(limit, 50))
        now = datetime.now(timezone.utc)

        stmt = (
            select(Membership)
            .options(
                selectinload(Membership.user),
                selectinload(Membership.game),
            )
            .where(
                Membership.vendor_id == vendor_id,
                Membership.plan == "trial",
                Membership.status == "active",
            )
            .order_by(Membership.trial_ends_at.asc())
            .limit(limit)
        )
        if game_slug:
            stmt = stmt.join(Game, Membership.game_id == Game.id).where(
                Game.vendor_id == vendor_id,
                Game.slug == game_slug,
            )

        rows = self._session.scalars(stmt).all()
        results: list[dict] = []
        for m in rows:
            # Prefer currently-active trials; still include if trial_ends_at is null
            if m.trial_ends_at is not None:
                ends = m.trial_ends_at
                if ends.tzinfo is None:
                    ends = ends.replace(tzinfo=timezone.utc)
                if ends < now:
                    continue
            user: AppUser | None = m.user
            game: Game | None = m.game
            results.append(
                {
                    "user_id": m.user_id,
                    "email": user.email if user else None,
                    "display_name": user.display_name if user else None,
                    "game_slug": game.slug if game else None,
                    "game_name": game.name if game else None,
                    "plan": m.plan,
                    "status": m.status,
                    "trial_ends_at": m.trial_ends_at.isoformat() if m.trial_ends_at else None,
                    "starts_at": m.starts_at.isoformat() if m.starts_at else None,
                }
            )
        return results[:limit]

    def get_membership(
        self,
        *,
        vendor_id: str,
        user_id: str,
        game_slug: str,
    ) -> dict | None:
        game = self._session.scalar(
            select(Game).where(Game.vendor_id == vendor_id, Game.slug == game_slug)
        )
        if game is None:
            return None
        m = self._session.scalar(
            select(Membership)
            .options(selectinload(Membership.user), selectinload(Membership.game))
            .where(
                Membership.vendor_id == vendor_id,
                Membership.user_id == user_id,
                Membership.game_id == game.id,
            )
        )
        if m is None:
            return None
        return {
            "id": m.id,
            "user_id": m.user_id,
            "email": m.user.email if m.user else None,
            "display_name": m.user.display_name if m.user else None,
            "game_slug": m.game.slug if m.game else game_slug,
            "game_name": m.game.name if m.game else None,
            "plan": m.plan,
            "status": m.status,
            "starts_at": m.starts_at.isoformat() if m.starts_at else None,
            "ends_at": m.ends_at.isoformat() if m.ends_at else None,
            "trial_ends_at": m.trial_ends_at.isoformat() if m.trial_ends_at else None,
        }
