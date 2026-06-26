from agents.base import BaseAgent
from state.models import AgentName, AgentResponse, ConversationState, EscalationTicket


class EscalationAgent(BaseAgent):
    name = AgentName.ESCALATION

    def run(self, message: str, conversation: ConversationState) -> AgentResponse:
        ticket = EscalationTicket(
            priority=classify_priority(message, conversation),
            sentiment=classify_sentiment(message),
            recommended_team=recommended_team(conversation),
            summary=summarize_context(message, conversation),
            context_snapshot={
                "conversation_id": conversation.conversation_id,
                "trace_id": conversation.trace_id,
                "customer_id": conversation.customer_id,
                "intent": conversation.current_intent,
                "entities": conversation.entities,
                "recent_messages": [item.content for item in conversation.messages[-6:]],
                "retrieved_sources": [
                    {"source_id": source.source_id, "title": source.title}
                    for source in conversation.retrieved_sources
                ],
            },
        )
        conversation.escalation_ticket = ticket

        return AgentResponse(
            agent=self.name,
            content=(
                f"I created escalation ticket {ticket.ticket_id} for the "
                f"{ticket.recommended_team} team with {ticket.priority} priority."
            ),
            confidence=0.9,
            escalation=ticket,
        )


def classify_priority(message: str, conversation: ConversationState) -> str:
    text = message.lower()
    if "high" in conversation.entities.get("urgency", "").lower():
        return "high"
    if any(term in text for term in ["immediate", "manager", "charged twice", "urgent"]):
        return "high"
    return "normal"


def classify_sentiment(message: str) -> str:
    text = message.lower()
    if any(term in text for term in ["frustrated", "angry", "manager", "immediate", "charged twice"]):
        return "frustrated"
    return "neutral"


def recommended_team(conversation: ConversationState) -> str:
    intent = conversation.current_intent or ""
    if "billing" in intent:
        return "human_billing_support"
    if "technical" in intent or "account" in intent:
        return "human_technical_support"
    return "human_support"


def summarize_context(message: str, conversation: ConversationState) -> str:
    parts = [
        f"Customer message: {message}",
        f"Intent: {conversation.current_intent or 'unknown'}",
    ]
    if conversation.entities:
        parts.append(f"Entities: {conversation.entities}")
    if conversation.retrieved_sources:
        sources = ", ".join(source.source_id for source in conversation.retrieved_sources)
        parts.append(f"Retrieved sources: {sources}")
    return " | ".join(parts)
