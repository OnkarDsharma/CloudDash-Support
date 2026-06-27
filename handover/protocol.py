"""Handover models and helpers will be added in a later phase."""

"""
handover/protocol.py

Handover protocol for cross-agent transitions.

Responsibilities:
- Detect multi-intent messages (e.g. SSO check + plan upgrade)
- Build HandoverPayload with full context preservation
- Log every handover event with structured fields
- Provide graceful fallback if target agent fails
"""

import logging
from datetime import UTC, datetime

from state.models import (
    AgentName,
    AgentResponse,
    ConversationState,
    HandoverPayload,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Multi-intent detection
# ---------------------------------------------------------------------------

# Each entry: (primary_intent_keywords, secondary_intent_keywords, primary_agent, secondary_agent)
_MULTI_INTENT_PATTERNS: list[tuple[list[str], list[str], AgentName, AgentName]] = [
    (
        ["sso", "login", "integration", "alert", "aws", "cloudwatch", "credential", "webhook", "dashboard"],
        ["upgrade", "downgrade" , "billing", "invoice", "payment"],
        AgentName.TECHNICAL,
        AgentName.BILLING,
    ),
    (
        ["upgrade", "downgrade", "billing"],
        ["sso", "integration", "alert", "aws", "api"],
        AgentName.BILLING,
        AgentName.TECHNICAL,
    ),
]


class MultiIntent:
    """Holds the result of a multi-intent detection."""

    def __init__(
        self,
        detected: bool,
        primary_agent: AgentName,
        secondary_agent: AgentName | None,
        reason: str,
    ) -> None:
        self.detected = detected
        self.primary_agent = primary_agent
        self.secondary_agent = secondary_agent
        self.reason = reason


def detect_multi_intent(message: str, conversation: ConversationState) -> MultiIntent:
    """
    Check whether the message contains two distinct intents that require
    different specialist agents.

    Returns a MultiIntent describing what was found.
    """
    text = message.lower()

    for primary_kws, secondary_kws, primary_agent, secondary_agent in _MULTI_INTENT_PATTERNS:
        has_primary = any(kw in text for kw in primary_kws)
        has_secondary = any(kw in text for kw in secondary_kws)

        if has_primary and has_secondary:
            reason = (
                f"Message contains keywords for both {primary_agent} "
                f"({[kw for kw in primary_kws if kw in text]}) "
                f"and {secondary_agent} "
                f"({[kw for kw in secondary_kws if kw in text]})"
            )
            logger.info(
                "multi_intent_detected",
                extra={
                    "trace_id": conversation.trace_id,
                    "primary_agent": primary_agent,
                    "secondary_agent": secondary_agent,
                    "reason": reason,
                },
            )
            return MultiIntent(
                detected=True,
                primary_agent=primary_agent,
                secondary_agent=secondary_agent,
                reason=reason,
            )

    return MultiIntent(
        detected=False,
        primary_agent=conversation.active_agent,
        secondary_agent=None,
        reason="single intent",
    )


# ---------------------------------------------------------------------------
# HandoverPayload construction
# ---------------------------------------------------------------------------

def create_handover_payload(
    conversation: ConversationState,
    source_agent: AgentName,
    target_agent: AgentName,
    reason: str,
    prior_response: AgentResponse | None = None,
) -> HandoverPayload:
    """
    Build a HandoverPayload that gives the receiving agent full context.
    Preserves: summary, entities, recent messages, retrieved sources.
    """
    recent_messages = (
        conversation.messages[-4:]
        if len(conversation.messages) >= 4
        else conversation.messages[:]
    )

    retrieved: list[RetrievalResult] = []
    if prior_response and prior_response.citations:
        retrieved = prior_response.citations
    elif conversation.retrieved_sources:
        retrieved = conversation.retrieved_sources

    payload = HandoverPayload(
        source_agent=source_agent,
        target_agent=target_agent,
        reason=reason,
        conversation_summary=conversation.summary,
        entities=dict(conversation.entities),
        recent_messages=recent_messages,
        retrieved_sources=retrieved,
        context_snapshot={
            "current_intent": conversation.current_intent,
            "status": conversation.status,
            "message_count": len(conversation.messages),
            "active_agent": conversation.active_agent,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    return payload


# ---------------------------------------------------------------------------
# Handover execution
# ---------------------------------------------------------------------------

def execute_handover(
    conversation: ConversationState,
    source_agent: AgentName,
    target_agent: AgentName,
    reason: str,
    prior_response: AgentResponse | None = None,
) -> HandoverPayload:
    """
    Record a handover event in conversation.handover_history and return
    the payload. This is the single place all handovers are logged.

    Caller is responsible for actually running the target agent.
    """
    payload = create_handover_payload(
        conversation=conversation,
        source_agent=source_agent,
        target_agent=target_agent,
        reason=reason,
        prior_response=prior_response,
    )

    conversation.handover_history.append(payload)
    conversation.active_agent = target_agent

    logger.info(
        "handover_executed",
        extra={
            "trace_id": conversation.trace_id,
            "handover_id": payload.id,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "reason": reason,
            "entities_transferred": list(payload.entities.keys()),
            "sources_transferred": len(payload.retrieved_sources),
            "timestamp": payload.timestamp.isoformat(),
        },
    )

    return payload


# ---------------------------------------------------------------------------
# Graceful fallback
# ---------------------------------------------------------------------------

def fallback_agent(conversation: ConversationState) -> AgentName:
    """
    Return the safest fallback agent when a handover target fails.
    Escalated conversations fall back to ESCALATION; others to TRIAGE.
    """
    from state.models import ConversationStatus  # local import to avoid circularity

    if conversation.status == ConversationStatus.ESCALATED:
        return AgentName.ESCALATION
    return AgentName.TRIAGE