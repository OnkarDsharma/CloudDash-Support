from email.mime import text

from agents.base import BaseAgent
from state.models import AgentName, AgentResponse, ConversationState


class TriageAgent(BaseAgent):
    name = AgentName.TRIAGE

    def run(self, message: str, conversation: ConversationState) -> AgentResponse:
        intent, target_agent = classify_intent(message, conversation)  # pass conversation
        entities = extract_entities(message)

        conversation.current_intent = intent
        conversation.entities.update(entities)
        conversation.active_agent = target_agent

        return AgentResponse(
            agent=self.name,
            content=f"Classified intent as {intent} and routed to {target_agent.value}.",
            confidence=0.82,
            metadata={
                "intent": intent,
                "target_agent": target_agent.value,
                "entities": entities,
            },
        )


def classify_intent(
    message: str,
    conversation: ConversationState | None = None,
) -> tuple[str, AgentName]:
    text = message.lower()

    if any(term in text for term in ["manager", "immediate refund", "charged twice", "duplicate"]):
        return "billing_escalation", AgentName.BILLING

    if any(term in text for term in ["escalate", "speak to a human", "speak to someone", "real person"]):
        return "escalation_requested", AgentName.ESCALATION


    # AFTER
    if any(term in text for term in ["datadog", "grafana", "splunk", "newrelic", "unsupported", "feature request"]):
        return "unsupported_integration", AgentName.ESCALATION

    # Score each agent domain
    scores = {
        AgentName.BILLING: 0,
        AgentName.TECHNICAL: 0,
    }

    billing_terms = ["charged", "invoice", "billing", "refund", "payment", "upgrade", "downgrade"]
    scores[AgentName.BILLING] += sum(1 for t in billing_terms if t in text)

    technical_terms = ["sso", "login", "rbac", "role", "alert", "aws", "api", "webhook",
                       "dashboard", "cloudwatch", "integration", "credential", "access"]
    scores[AgentName.TECHNICAL] += sum(1 for t in technical_terms if t in text)

    # No keyword signal — fall back to previous intent in the conversation
    if scores[AgentName.BILLING] == 0 and scores[AgentName.TECHNICAL] == 0:
        if conversation and conversation.current_intent:
            prior = conversation.current_intent
            if "billing" in prior:
                return prior, AgentName.BILLING
            if prior in ("technical_issue", "account_access"):
                return prior, AgentName.TECHNICAL
        return "general_inquiry", AgentName.TECHNICAL

    # Pick winner — technical wins on a tie (safer default)
    if scores[AgentName.TECHNICAL] >= scores[AgentName.BILLING]:
        return "technical_issue", AgentName.TECHNICAL
    else:
        return "billing_question", AgentName.BILLING


def extract_entities(message: str) -> dict[str, str]:
    text = message.lower()
    entities: dict[str, str] = {}

    for plan in ["starter", "pro", "enterprise"]:
        if plan in text:
            entities["plan"] = plan.title()

    for provider in ["aws", "gcp", "azure", "datadog"]:
        if provider in text:
            entities["cloud_provider"] = provider.upper() if provider != "datadog" else "Datadog"

    if "sso" in text:
        entities["product_area"] = "SSO"
    elif "alert" in text:
        entities["product_area"] = "Alerts"
    elif "invoice" in text or "charged" in text:
        entities["product_area"] = "Billing"

    if any(term in text for term in ["immediate", "manager", "urgent", "charged twice"]):
        entities["urgency"] = "high"

    return entities