"""Chat session and message routes — Phase 1 (read copilot agent)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limiter import rate_limit_dependency
from app.db.session import get_db
from app.deps import get_vendor_context
from app.domain.models import ChatMessage, ChatSession
from app.domain.schemas import (
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatTurnResponse,
    VendorContext,
)
from app.services import chat_service

router = APIRouter()


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: ChatSessionCreate,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Open a new chat session for the authenticated vendor user."""
    session = ChatSession(
        id=_new_id("cs"),
        vendor_id=ctx.vendor_id,
        vendor_user_id=ctx.vendor_user_id,
        created_at=_utcnow(),
    )
    db.add(session)
    await db.flush()

    return ChatSessionResponse(
        id=session.id,
        vendor_id=session.vendor_id,
        vendor_user_id=session.vendor_user_id,
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Retrieve a single chat session (vendor-scoped)."""
    session = await chat_service.get_session_for_vendor(
        db, session_id=session_id, vendor_id=ctx.vendor_id
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions/{session_id}/messages", response_model=ChatMessageListResponse)
async def list_messages(
    session_id: str,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageListResponse:
    """Return message history for a session (vendor-scoped)."""
    session = await chat_service.get_session_for_vendor(
        db, session_id=session_id, vendor_id=ctx.vendor_id
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = (
        await db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
    ).all()

    return ChatMessageListResponse(
        session_id=session_id,
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    session_id: str,
    body: ChatMessageCreate,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_dependency),
) -> ChatTurnResponse:
    """Post a user message, run the read copilot, return the full turn."""
    session = await chat_service.get_session_for_vendor(
        db, session_id=session_id, vendor_id=ctx.vendor_id
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    user_msg, assistant_msg = await chat_service.handle_user_message(
        db, session=session, ctx=ctx, content=body.content
    )

    return ChatTurnResponse(
        session_id=session_id,
        user_message=ChatMessageResponse.model_validate(user_msg),
        assistant_message=ChatMessageResponse.model_validate(assistant_msg),
    )


@router.post("/sessions/{session_id}/messages:stream")
async def post_message_stream(
    session_id: str,
    body: ChatMessageCreate,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_dependency),
) -> StreamingResponse:
    """SSE stream for a chat turn: status events + final result.

    Practical Phase 1 approach (CrewAI is not token-streaming end-to-end):
    emit phase status, then a single result event with text + blocks.
    """
    session = await chat_service.get_session_for_vendor(
        db, session_id=session_id, vendor_id=ctx.vendor_id
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    async def event_gen() -> AsyncIterator[str]:
        yield _sse("status", {"phase": "routing"})
        yield _sse("status", {"phase": "running"})

        user_msg, assistant_msg = await chat_service.handle_user_message(
            db, session=session, ctx=ctx, content=body.content
        )

        content = assistant_msg.content if isinstance(assistant_msg.content, dict) else {}
        yield _sse(
            "result",
            {
                "text": content.get("text", ""),
                "blocks": content.get("blocks", []),
                "tool_traces": content.get("tool_traces", []),
                "user_message_id": user_msg.id,
                "assistant_message_id": assistant_msg.id,
            },
        )
        yield _sse("done", {"message_id": assistant_msg.id, "session_id": session_id})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
