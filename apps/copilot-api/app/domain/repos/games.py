from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Game


class GamesRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_games(self, *, vendor_id: str) -> list[dict]:
        rows = self._session.scalars(
            select(Game).where(Game.vendor_id == vendor_id).order_by(Game.slug.asc())
        ).all()
        return [{"id": g.id, "slug": g.slug, "name": g.name} for g in rows]

    def get_by_slug(self, *, vendor_id: str, slug: str) -> Game | None:
        return self._session.scalar(
            select(Game).where(Game.vendor_id == vendor_id, Game.slug == slug)
        )
