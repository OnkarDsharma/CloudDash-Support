"""
tests/test_handover.py
"""

from unittest.mock import MagicMock

import pytest

from handover.protocol import (
    create_handover_payload,
    detect_multi_intent,
    execute_handover,
    fallback_agent,
)
from state.models import (
    AgentName,
    AgentResponse,
    ConversationState,
    ConversationStatus,
    Message,
    MessageRole,
)


def _conv(**kwargs) -> ConversationState:
    return ConversationState(customer_id="cust-test", **kwargs)


def _response(agent: AgentName) -> AgentResponse:
    return AgentResponse(agent=agent, content="ok")


# ---------------------------------------------------------------------------
# detect_multi_intent
# ---------------------------------------------------------------------------

class TestDetectMultiIntent:
    def test_sso_plus_upgrade_detected(self):
        conv = _conv()
        result = detect_multi_intent(
            "I want to upgrade from Pro to Enterprise but first check my SSO issue",
            conv,
        )
        assert result.detected is True
        assert result.primary_agent == AgentName.TECHNICAL
        assert result.secondary_agent == AgentName.BILLING

    def test_billing_plus_technical_detected(self):
        conv = _conv()
        result = detect_multi_intent(
            "I have a billing question and also an alert is not firing",
            conv,
        )
        assert result.detected is True

    def test_single_intent_not_detected(self):
        conv = _conv()
        result = detect_multi_intent("My AWS alerts stopped firing", conv)
        assert result.detected is False
        assert result.secondary_agent is None

    def test_pure_billing_single_intent(self):
        conv = _conv()
        result = detect_multi_intent("I need to upgrade my plan", conv)
        assert result.detected is False


# ---------------------------------------------------------------------------
# create_handover_payload
# ---------------------------------------------------------------------------

class TestCreateHandoverPayload:
    def test_entities_preserved(self):
        conv = _conv()
        conv.entities = {"plan": "Pro", "product_area": "SSO"}
        conv.summary = "Customer wants to upgrade after SSO fix"

        payload = create_handover_payload(
            conversation=conv,
            source_agent=AgentName.TECHNICAL,
            target_agent=AgentName.BILLING,
            reason="multi-intent: billing follow-up",
        )

        assert payload.entities["plan"] == "Pro"
        assert payload.entities["product_area"] == "SSO"
        assert payload.conversation_summary == conv.summary

    def test_recent_messages_capped_at_four(self):
        conv = _conv()
        for i in range(6):
            conv.add_message(Message(role=MessageRole.CUSTOMER, content=f"msg {i}"))

        payload = create_handover_payload(
            conversation=conv,
            source_agent=AgentName.TECHNICAL,
            target_agent=AgentName.BILLING,
            reason="test",
        )

        assert len(payload.recent_messages) == 4

    def test_citations_from_prior_response(self):
        from state.models import RetrievalResult

        conv = _conv()
        prior = AgentResponse(
            agent=AgentName.TECHNICAL,
            content="ok",
            citations=[
                RetrievalResult(
                    source_id="KB-011",
                    title="SSO Setup",
                    category="account_access",
                    snippet="SSO steps...",
                )
            ],
        )

        payload = create_handover_payload(
            conversation=conv,
            source_agent=AgentName.TECHNICAL,
            target_agent=AgentName.BILLING,
            reason="test",
            prior_response=prior,
        )

        assert len(payload.retrieved_sources) == 1
        assert payload.retrieved_sources[0].source_id == "KB-011"

    def test_context_snapshot_fields(self):
        conv = _conv()
        conv.current_intent = "account_access"

        payload = create_handover_payload(
            conversation=conv,
            source_agent=AgentName.TECHNICAL,
            target_agent=AgentName.BILLING,
            reason="test",
        )

        assert payload.context_snapshot["current_intent"] == "account_access"
        assert "timestamp" in payload.context_snapshot


# ---------------------------------------------------------------------------
# execute_handover
# ---------------------------------------------------------------------------

class TestExecuteHandover:
    def test_appended_to_history(self):
        conv = _conv()
        execute_handover(
            conversation=conv,
            source_agent=AgentName.TRIAGE,
            target_agent=AgentName.TECHNICAL,
            reason="routed by triage",
        )
        assert len(conv.handover_history) == 1
        assert conv.handover_history[0].source_agent == AgentName.TRIAGE

    def test_active_agent_updated(self):
        conv = _conv()
        execute_handover(
            conversation=conv,
            source_agent=AgentName.TECHNICAL,
            target_agent=AgentName.BILLING,
            reason="multi-intent",
        )
        assert conv.active_agent == AgentName.BILLING

    def test_multiple_handovers_accumulate(self):
        conv = _conv()
        execute_handover(conv, AgentName.TRIAGE, AgentName.TECHNICAL, "triage")
        execute_handover(conv, AgentName.TECHNICAL, AgentName.BILLING, "multi-intent")
        execute_handover(conv, AgentName.BILLING, AgentName.ESCALATION, "escalation")

        assert len(conv.handover_history) == 3
        assert conv.handover_history[2].target_agent == AgentName.ESCALATION


# ---------------------------------------------------------------------------
# fallback_agent
# ---------------------------------------------------------------------------

class TestFallbackAgent:
    def test_escalated_conversation_falls_back_to_escalation(self):
        conv = _conv(status=ConversationStatus.ESCALATED)
        assert fallback_agent(conv) == AgentName.ESCALATION

    def test_active_conversation_falls_back_to_triage(self):
        conv = _conv(status=ConversationStatus.ACTIVE)
        assert fallback_agent(conv) == AgentName.TRIAGE