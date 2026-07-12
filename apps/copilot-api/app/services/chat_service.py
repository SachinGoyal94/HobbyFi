"""Chat service: persist messages and invoke the read copilot agent."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ChatMessage, ChatSession
from app.domain.schemas import VendorContext

logger = logging.getLogger(__name__)

# Injectable agent runner — tests replace this to avoid real Gemini calls.
AgentRunner = Callable[..., Any]  # awaitable


async def _default_agent_runner(
    *,
    user_message: str,
    ctx: VendorContext,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    message_id: str | None = None,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    from app.agent.crew import run_copilot_turn

    return await run_copilot_turn(
        user_message=user_message, ctx=ctx, history=history, session_id=session_id, message_id=message_id, db=db
    )


_agent_runner: AgentRunner = _default_agent_runner


def set_agent_runner(runner: AgentRunner | None) -> None:
    """Override the agent runner (tests). Pass None to restore default."""
    global _agent_runner
    _agent_runner = runner or _default_agent_runner


def get_agent_runner() -> AgentRunner:
    return _agent_runner


async def get_session_for_vendor(
    db: AsyncSession,
    *,
    session_id: str,
    vendor_id: str,
) -> ChatSession | None:
    return await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.vendor_id == vendor_id,
        )
    )


async def load_history(
    db: AsyncSession,
    *,
    session_id: str,
    limit: int = 12,
) -> list[dict[str, str]]:
    messages = (
        await db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
    ).all()
    history: list[dict[str, str]] = []
    for m in messages[-limit:]:
        text = ""
        if isinstance(m.content, dict):
            text = str(m.content.get("text") or "")
        history.append({"role": m.role, "content": text})
    return history


async def handle_user_message(
    db: AsyncSession,
    *,
    session: ChatSession,
    ctx: VendorContext,
    content: str,
) -> tuple[ChatMessage, ChatMessage]:
    """Persist user message, run agent, persist assistant message.

    Returns (user_message, assistant_message).
    """
    user_msg = ChatMessage(
        id=_new_id("m"),
        session_id=session.id,
        role="user",
        content={"text": content},
        created_at=_utcnow(),
    )
    db.add(user_msg)
    await db.flush()

    history = await load_history(db, session_id=session.id)
    # Exclude the just-added user message from "recent" history for the prompt
    # (it's passed separately as user_message). Keep prior turns only.
    prior = history[:-1] if history and history[-1]["role"] == "user" else history

    try:
        agent_result = await _agent_runner(
            user_message=content,
            ctx=ctx,
            history=prior,
            session_id=session.id,
            message_id=user_msg.id,
            db=db,
        )
    except Exception as exc:
        logger.exception("agent_turn_failed session_id=%s", session.id)
        agent_result = {
            "text": (
                "Sorry — I hit an error while answering. "
                "Please try again in a moment."
            ),
            "blocks": [],
            "tool_traces": [],
            "error": str(exc),
        }

    assistant_content: dict[str, Any] = {
        "text": agent_result.get("text") or "",
        "blocks": agent_result.get("blocks") or [],
    }
    if agent_result.get("tool_traces"):
        assistant_content["tool_traces"] = agent_result["tool_traces"]
    if agent_result.get("error"):
        assistant_content["error"] = agent_result["error"]

    assistant_msg = ChatMessage(
        id=_new_id("m"),
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        created_at=_utcnow(),
    )
    db.add(assistant_msg)
    await db.flush()

    # Lightweight audit row for the turn
    try:
        from app.domain.models import AuditEvent

        db.add(
            AuditEvent(
                id=_new_id("ae"),
                vendor_id=ctx.vendor_id,
                actor_id=ctx.vendor_user_id,
                event_type="copilot.turn",
                entity_type="chat_session",
                entity_id=session.id,
                metadata_json={
                    "user_message_id": user_msg.id,
                    "assistant_message_id": assistant_msg.id,
                    "tools": [
                        t.get("tool") for t in (agent_result.get("tool_traces") or [])
                    ],
                },
                created_at=_utcnow(),
            )
        )
        await db.flush()
    except Exception:
        logger.exception("audit_write_failed session_id=%s", session.id)

    return user_msg, assistant_msg


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
