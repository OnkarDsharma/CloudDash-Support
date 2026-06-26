from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class AgentName(StrEnum):
    TRIAGE = "triage"
    TECHNICAL = "technical"
    BILLING = "billing"
    ESCALATION = "escalation"


class MessageRole(StrEnum):
    CUSTOMER = "customer"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    CLOSED = "closed"


class RetrievalResult(BaseModel):
    source_id: str
    title: str
    category: str
    snippet: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: str
    agent: AgentName | None = None
    citations: list[RetrievalResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class AgentResponse(BaseModel):
    agent: AgentName
    content: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    citations: list[RetrievalResult] = Field(default_factory=list)
    handover: "HandoverPayload | None" = None
    escalation: "EscalationTicket | None" = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoverPayload(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=utc_now)
    source_agent: AgentName
    target_agent: AgentName
    reason: str
    conversation_summary: str = ""
    entities: dict[str, Any] = Field(default_factory=dict)
    recent_messages: list[Message] = Field(default_factory=list)
    retrieved_sources: list[RetrievalResult] = Field(default_factory=list)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)


class EscalationTicket(BaseModel):
    ticket_id: str = Field(default_factory=lambda: f"ESC-{uuid4().hex[:8].upper()}")
    priority: str
    sentiment: str | None = None
    recommended_team: str
    summary: str
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ConversationState(BaseModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str | None = None
    active_agent: AgentName = AgentName.TRIAGE
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: list[Message] = Field(default_factory=list)
    summary: str = ""
    entities: dict[str, Any] = Field(default_factory=dict)
    current_intent: str | None = None
    retrieved_sources: list[RetrievalResult] = Field(default_factory=list)
    handover_history: list[HandoverPayload] = Field(default_factory=list)
    escalation_ticket: EscalationTicket | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = utc_now()
