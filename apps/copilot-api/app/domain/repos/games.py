from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Game


class GamesRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_games(self, *, vendor_id: str) -> list[dict]:
        rows = (await self._session.scalars(
            select(Game).where(Game.vendor_id == vendor_id).order_by(Game.slug.asc())
        )).all()
        return [{"id": g.id, "slug": g.slug, "name": g.name} for g in rows]

    async def get_by_slug(self, *, vendor_id: str, slug: str) -> Game | None:
        return await self._session.scalar(
            select(Game).where(Game.vendor_id == vendor_id, Game.slug == slug)
        )
