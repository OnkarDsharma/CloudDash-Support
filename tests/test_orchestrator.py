"""
agents/orchestrator.py

Central orchestration layer. api/routes.py delegates all agent logic here.
"""

import logging
from datetime import UTC, datetime

from agents.billing import BillingAgent
from agents.escalation import EscalationAgent
from agents.technical import TechnicalSupportAgent
from agents.triage import TriageAgent
from retrieval.retriever import KnowledgeBaseRetriever
from state.models import (
    AgentName,
    AgentResponse,
    ConversationState,
    ConversationStatus,
    HandoverPayload,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Runs the full agent pipeline for a single customer message turn.

    Flow:
        1. TriageAgent classifies intent and sets conversation.active_agent
        2. Specialist agent (Technical / Billing / Escalation) handles the message
        3. If specialist flags needs_escalation, EscalationAgent takes over
        4. HandoverPayload is logged whenever the active agent changes
        5. Returns the final AgentResponse (caller adds it to conversation)
    """

    def __init__(self, retriever: KnowledgeBaseRetriever | None = None) -> None:
        retriever = retriever or KnowledgeBaseRetriever()
        self.triage = TriageAgent(retriever=retriever)
        self.technical = TechnicalSupportAgent(retriever=retriever)
        self.billing = BillingAgent(retriever=retriever)
        self.escalation = EscalationAgent(retriever=retriever)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def handle(self, message: str, conversation: ConversationState) -> AgentResponse:
        """
        Process one customer message and return the final AgentResponse.
        ConversationState is mutated in place (active_agent, status,
        entities, handover_history).  Caller is responsible for
        persisting state and appending the assistant Message.
        """
        prior_agent = conversation.active_agent

        # 1. Triage: classify + route (updates conversation.active_agent)
        triage_response = self.triage.run(message, conversation)
        logger.info(
            "triage_complete",
            extra={
                "trace_id": conversation.trace_id,
                "intent": conversation.current_intent,
                "routed_to": conversation.active_agent,
            },
        )

        # 2. Specialist agent
        agent_response = self._run_specialist(message, conversation)

        # 3. Log handover if agent changed after triage
        if conversation.active_agent != prior_agent:
            self._record_handover(
                conversation=conversation,
                source=prior_agent,
                target=conversation.active_agent,
                reason=f"Triage routed intent '{conversation.current_intent}' to {conversation.active_agent}",
                prior_response=triage_response,
            )

        # 4. Escalation if specialist requests it
        if agent_response.metadata.get("needs_escalation"):
            escalation_source = conversation.active_agent
            agent_response = self._escalate(message, conversation, triggered_by=agent_response)
            self._record_handover(
                conversation=conversation,
                source=escalation_source,
                target=AgentName.ESCALATION,
                reason=agent_response.metadata.get("escalation_reason", "specialist requested escalation"),
                prior_response=agent_response,
            )

        return agent_response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_specialist(self, message: str, conversation: ConversationState) -> AgentResponse:
        agent_map = {
            AgentName.BILLING: self.billing,
            AgentName.ESCALATION: self.escalation,
            AgentName.TECHNICAL: self.technical,
            AgentName.TRIAGE: self.technical,  # fallback: triage shouldn't be final
        }
        agent = agent_map.get(conversation.active_agent, self.technical)
        response = agent.run(message, conversation)
        logger.info(
            "specialist_response",
            extra={
                "trace_id": conversation.trace_id,
                "agent": response.agent,
                "citations": len(response.citations),
                "needs_escalation": response.metadata.get("needs_escalation", False),
            },
        )
        return response

    def _escalate(
        self,
        message: str,
        conversation: ConversationState,
        triggered_by: AgentResponse,
    ) -> AgentResponse:
        conversation.active_agent = AgentName.ESCALATION
        conversation.status = ConversationStatus.ESCALATED
        response = self.escalation.run(message, conversation)
        if response.escalation:
            conversation.escalation_ticket = response.escalation
        logger.info(
            "escalation_triggered",
            extra={
                "trace_id": conversation.trace_id,
                "ticket_id": response.escalation.ticket_id if response.escalation else None,
            },
        )
        return response

    def _record_handover(
        self,
        conversation: ConversationState,
        source: AgentName,
        target: AgentName,
        reason: str,
        prior_response: AgentResponse,
    ) -> None:
        """Append a HandoverPayload to conversation.handover_history."""
        recent = conversation.messages[-4:] if len(conversation.messages) >= 4 else conversation.messages[:]

        payload = HandoverPayload(
            source_agent=source,
            target_agent=target,
            reason=reason,
            conversation_summary=conversation.summary,
            entities=dict(conversation.entities),
            recent_messages=recent,
            retrieved_sources=prior_response.citations,
            context_snapshot={
                "current_intent": conversation.current_intent,
                "status": conversation.status,
                "message_count": len(conversation.messages),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        conversation.handover_history.append(payload)
        logger.info(
            "handover_recorded",
            extra={
                "trace_id": conversation.trace_id,
                "handover_id": payload.id,
                "source": source,
                "target": target,
                "reason": reason,
            },
        )