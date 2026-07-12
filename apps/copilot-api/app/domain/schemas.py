from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --- Auth / context ---

Role = Literal["owner", "admin", "support", "viewer"]


class VendorContext(BaseModel):
    """Authenticated portal user context. Source of tenancy — never trust the LLM."""

    vendor_id: str
    vendor_user_id: str
    email: str
    role: Role
    timezone: str = "UTC"
    vendor_name: str = ""


class VendorContextResponse(VendorContext):
    """Public echo of the current auth context."""

    pass


# --- Chat ---

MessageRole = Literal["user", "assistant", "tool", "system"]


class ChatSessionCreate(BaseModel):
    """Optional client metadata when opening a session."""

    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSessionResponse(BaseModel):
    id: str
    vendor_id: str
    vendor_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    """User message for a chat turn. Agent reply is generated server-side."""

    content: str = Field(..., min_length=1, max_length=16_000)


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageListResponse(BaseModel):
    session_id: str
    messages: list[ChatMessageResponse]


class ChatTurnResponse(BaseModel):
    """Result of POST /messages: user message + assistant reply with UI blocks."""

    session_id: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


# --- Health / meta ---

class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    version: str
    gemini_model: str
    gemini_configured: bool
    database: str


class SeedSummary(BaseModel):
    vendors: int
    vendor_users: int
    games: int
    app_users: int
    memberships: int
    revenue_rows: int


# --- Action proposals (Phase 2: write → approve → execute) ---

ProposalStatus = Literal[
    "pending", "approved", "executed", "failed", "rejected", "expired", "cancelled"
]
ProposalAction = Literal[
    "extend_trial", "update_membership_dates", "change_plan", "suspend_user"
]
ProposalDecision = Literal["approve", "reject"]


class ActionProposalCreate(BaseModel):
    """Args from a propose_* tool — never directly from the client."""

    action_type: ProposalAction
    payload: dict[str, Any]
    preview: dict[str, Any]


class ActionProposalResponse(BaseModel):
    id: str
    vendor_id: str
    session_id: str | None
    message_id: str | None
    proposed_by: str
    action_type: ProposalAction
    payload: dict[str, Any]
    preview: dict[str, Any]
    status: ProposalStatus
    idempotency_key: str
    expires_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    execution_result: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProposalDecisionRequest(BaseModel):
    decision: ProposalDecision
    reason: str | None = None


class ProposalListResponse(BaseModel):
    proposals: list[ActionProposalResponse]
    count: int


# --- Audit (Phase 2) ---

class AuditEventResponse(BaseModel):
    id: str
    vendor_id: str
    actor_id: str | None = None
    event_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditListResponse(BaseModel):
    events: list[AuditEventResponse]
    count: int
