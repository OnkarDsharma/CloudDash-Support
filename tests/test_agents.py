from agents.billing import BillingAgent
from agents.escalation import EscalationAgent
from agents.technical import TechnicalSupportAgent
from agents.triage import TriageAgent
from state.models import AgentName, ConversationState


def test_triage_routes_technical_issue() -> None:
    conversation = ConversationState()
    response = TriageAgent().run(
        "My CloudDash alerts stopped firing after an AWS credential update.",
        conversation,
    )

    assert response.metadata["intent"] == "technical_issue"
    assert response.metadata["target_agent"] == "technical"
    assert conversation.active_agent == AgentName.TECHNICAL
    assert conversation.entities["cloud_provider"] == "AWS"


def test_triage_routes_billing_issue() -> None:
    conversation = ConversationState()
    response = TriageAgent().run(
        "I was charged twice for April and need an immediate refund.",
        conversation,
    )

    assert response.metadata["intent"] == "billing_escalation"
    assert response.metadata["target_agent"] == "billing"
    assert conversation.active_agent == AgentName.BILLING
    assert conversation.entities["urgency"] == "high"


def test_technical_agent_returns_citations() -> None:
    conversation = ConversationState(current_intent="technical_issue")

    response = TechnicalSupportAgent().run(
        "CloudDash alerts stopped firing after AWS credentials were updated.",
        conversation,
    )

    assert response.agent == AgentName.TECHNICAL
    assert response.citations
    assert response.citations[0].source_id == "KB-005"


def test_billing_agent_flags_duplicate_charge_for_escalation() -> None:
    conversation = ConversationState(current_intent="billing_escalation")

    response = BillingAgent().run(
        "I was charged twice for April and need an immediate refund and manager.",
        conversation,
    )

    assert response.agent == AgentName.BILLING
    assert response.metadata["needs_escalation"] is True
    assert response.citations


def test_escalation_agent_creates_ticket() -> None:
    conversation = ConversationState(
        customer_id="cust_123",
        current_intent="billing_escalation",
        entities={"urgency": "high"},
    )

    response = EscalationAgent().run(
        "I was charged twice and need a manager.",
        conversation,
    )

    assert response.agent == AgentName.ESCALATION
    assert response.escalation is not None
    assert response.escalation.priority == "high"
    assert response.escalation.recommended_team == "human_billing_support"
