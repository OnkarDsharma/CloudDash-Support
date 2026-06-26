from agents.base import BaseAgent, format_citations
from state.models import AgentName, AgentResponse, ConversationState


class BillingAgent(BaseAgent):
    name = AgentName.BILLING

    def run(self, message: str, conversation: ConversationState) -> AgentResponse:
        citations = self.retriever.retrieve(message, conversation=conversation, top_k=3)
        conversation.retrieved_sources = citations

        lower_message = message.lower()
        should_escalate = any(
            term in lower_message
            for term in ["immediate refund", "manager", "charged twice", "duplicate charge"]
        )

        if not citations:
            return AgentResponse(
                agent=self.name,
                content=(
                    "I could not find a CloudDash billing policy that supports a confident answer. "
                    "I can escalate this to a human billing specialist."
                ),
                confidence=0.2,
                citations=[],
                metadata={"needs_escalation": True},
            )

        primary = citations[0]
        if should_escalate:
            content = (
                "I found the relevant billing policy, and this case should be escalated "
                "because immediate refunds, duplicate charges, or manager requests require a human billing specialist. "
                f"{primary.snippet}{format_citations(AgentResponse(agent=self.name, content='', citations=citations))}"
            )
        else:
            technical_context = ""
            if conversation.handover_history:
                last_handover = conversation.handover_history[-1]
                technical_sources = [
                    s for s in last_handover.retrieved_sources
                    if s.category in ("troubleshooting", "api_documentation")
                ]
                if technical_sources:
                    tech = technical_sources[0]
                    technical_context = (
                        f"\n\nRegarding your technical question — "
                        f"based on {tech.source_id}: {tech.snippet[:200]}..."
                    )

            content = (
                f"I found the most relevant billing guidance in {primary.source_id}. "
                f"{primary.snippet} "
                "I will only use documented CloudDash billing policy for this answer."
                f"{technical_context}"
                f"{format_citations(AgentResponse(agent=self.name, content='', citations=citations))}"
            )


        return AgentResponse(
            agent=self.name,
            content=content,
            confidence=min(primary.score or 0.0, 0.95),
            citations=citations,
            metadata={"needs_escalation": should_escalate},
        )
