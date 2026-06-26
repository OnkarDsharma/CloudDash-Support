from agents.base import BaseAgent, format_citations
from state.models import AgentName, AgentResponse, ConversationState


class TechnicalSupportAgent(BaseAgent):
    name = AgentName.TECHNICAL

    def run(self, message: str, conversation: ConversationState) -> AgentResponse:
        citations = self.retriever.retrieve(message, conversation=conversation, top_k=3)
        conversation.retrieved_sources = citations

        if not citations:
            return AgentResponse(
                agent=self.name,
                content=(
                    "I could not find a CloudDash knowledge base article that supports "
                    "a confident technical answer. I can escalate this to human support."
                ),
                confidence=0.2,
                citations=[],
                metadata={"needs_escalation": True},
            )

        primary = citations[0]
        content = (
            f"I found the most relevant technical guidance in {primary.source_id}. "
            f"{primary.snippet} "
            "Please follow those checks in order, then re-test after one full evaluation window if alerts or metrics are involved."
            f"{format_citations(AgentResponse(agent=self.name, content='', citations=citations))}"
        )

        return AgentResponse(
            agent=self.name,
            content=content,
            confidence=min(primary.score or 0.0, 0.95),
            citations=citations,
        )
