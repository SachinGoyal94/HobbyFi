"""Chat session and message routes — Phase 0 (storage only, no agent yet)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_vendor_context
from app.domain.models import ChatMessage, ChatSession
from app.domain.schemas import (
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    VendorContext,
)

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
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.vendor_id == ctx.vendor_id,
        )
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
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.vendor_id == ctx.vendor_id,
        )
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


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def post_message(
    session_id: str,
    body: ChatMessageCreate,
    ctx: VendorContext = Depends(get_vendor_context),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    """Post a user message to a session.

    Phase 0: stores the message only (returns it persisted).
    Phase 1: this will also invoke the agent and return the assistant response
    alongside SSE streaming events at `/messages:stream`.
    """
    # Verify session ownership
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.vendor_id == ctx.vendor_id,
        )
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msg = ChatMessage(
        id=_new_id("m"),
        session_id=session_id,
        role="user",
        content={"text": body.content},
        created_at=_utcnow(),
    )
    db.add(msg)
    await db.flush()

    return ChatMessageResponse.model_validate(msg)



def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)