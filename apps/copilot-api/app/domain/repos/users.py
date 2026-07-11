from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.models import AppUser, Game, Membership


class UsersRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        *,
        vendor_id: str,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        q = query.strip()
        if not q:
            return []
        limit = max(1, min(limit, 50))
        pattern = f"%{q}%"
        rows = self._session.scalars(
            select(AppUser)
            .where(
                AppUser.vendor_id == vendor_id,
                or_(
                    AppUser.id.ilike(pattern),
                    AppUser.email.ilike(pattern),
                    AppUser.display_name.ilike(pattern),
                ),
            )
            .order_by(AppUser.id.asc())
            .limit(limit)
        ).all()
        return [_user_dict(u) for u in rows]

    def get_user(self, *, vendor_id: str, user_id: str) -> dict | None:
        user = self._session.scalar(
            select(AppUser)
            .options(selectinload(AppUser.memberships).selectinload(Membership.game))
            .where(AppUser.vendor_id == vendor_id, AppUser.id == user_id)
        )
        if user is None:
            return None
        payload = _user_dict(user)
        payload["memberships"] = [
            {
                "id": m.id,
                "game_id": m.game_id,
                "game_slug": m.game.slug if m.game else None,
                "game_name": m.game.name if m.game else None,
                "plan": m.plan,
                "status": m.status,
                "starts_at": m.starts_at.isoformat() if m.starts_at else None,
                "ends_at": m.ends_at.isoformat() if m.ends_at else None,
                "trial_ends_at": m.trial_ends_at.isoformat() if m.trial_ends_at else None,
            }
            for m in user.memberships
            if m.vendor_id == vendor_id
        ]
        return payload


def _user_dict(u: AppUser) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "status": u.status,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }
