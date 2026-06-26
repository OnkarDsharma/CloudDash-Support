"""
agents/orchestrator.py

Central orchestration layer. api/routes.py delegates all agent logic here.
"""

import logging

from agents.billing import BillingAgent
from agents.escalation import EscalationAgent
from agents.technical import TechnicalSupportAgent
from agents.triage import TriageAgent
from handover.protocol import detect_multi_intent, execute_handover, fallback_agent
from retrieval.retriever import KnowledgeBaseRetriever
from state.models import (
    AgentName,
    AgentResponse,
    ConversationState,
    ConversationStatus,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Runs the full agent pipeline for a single customer message turn.

    Single-intent flow:
        Triage -> Specialist -> (optional) Escalation

    Multi-intent flow (e.g. Scenario 2 - SSO check + plan upgrade):
        Triage -> Primary Specialist -> Handover -> Secondary Specialist
        If secondary also needs escalation -> Escalation Agent

    HandoverPayload is recorded in conversation.handover_history at every
    agent transition via handover/protocol.py.
    """

    def __init__(self, retriever: KnowledgeBaseRetriever | None = None) -> None:
        retriever = retriever or KnowledgeBaseRetriever()
        self.triage = TriageAgent(retriever=retriever)
        self.technical = TechnicalSupportAgent(retriever=retriever)
        self.billing = BillingAgent(retriever=retriever)
        self.escalation = EscalationAgent(retriever=retriever)

        self._agent_map: dict[AgentName, object] = {
            AgentName.TECHNICAL: self.technical,
            AgentName.BILLING: self.billing,
            AgentName.ESCALATION: self.escalation,
            AgentName.TRIAGE: self.technical,  # triage is never a final responder
        }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def handle(self, message: str, conversation: ConversationState) -> AgentResponse:
        """
        Process one customer message and return the final AgentResponse.
        Mutates ConversationState (active_agent, status, entities,
        handover_history). Caller appends the assistant Message and persists.
        """
        prior_agent = conversation.active_agent

        # 1. Triage
        self.triage.run(message, conversation)
        logger.info(
            "triage_complete",
            extra={
                "trace_id": conversation.trace_id,
                "intent": conversation.current_intent,
                "routed_to": conversation.active_agent,
            },
        )

        # 2. Record handover if triage changed the active agent
        if conversation.active_agent != prior_agent:
            execute_handover(
                conversation=conversation,
                source_agent=prior_agent,
                target_agent=conversation.active_agent,
                reason=f"Triage routed intent '{conversation.current_intent}' to {conversation.active_agent}",
            )

        # 3. Detect multi-intent BEFORE running the primary specialist
        multi = detect_multi_intent(message, conversation)

        # 4. Run primary specialist
        primary_response = self._run_specialist(message, conversation)

        # 5. Escalate if primary specialist requests it
        if primary_response.metadata.get("needs_escalation"):
            return self._escalate(
                message=message,
                conversation=conversation,
                source_agent=conversation.active_agent,
                prior_response=primary_response,
                reason=primary_response.metadata.get("escalation_reason", "specialist requested escalation"),
            )

        # 6. If multi-intent: hand over to secondary specialist
        if multi.detected and multi.secondary_agent:
            secondary_response = self._run_secondary(
                message=message,
                conversation=conversation,
                primary_response=primary_response,
                secondary_agent=multi.secondary_agent,
                handover_reason=multi.reason,
            )
            if secondary_response.metadata.get("needs_escalation"):
                return self._escalate(
                    message=message,
                    conversation=conversation,
                    source_agent=multi.secondary_agent,
                    prior_response=secondary_response,
                    reason="secondary agent requested escalation",
                )
            return secondary_response

        return primary_response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_specialist(self, message: str, conversation: ConversationState) -> AgentResponse:
        agent = self._agent_map.get(conversation.active_agent, self.technical)
        response = agent.run(message, conversation)

        # If escalation agent ran directly, mark conversation as escalated
        if conversation.active_agent == AgentName.ESCALATION:
            conversation.status = ConversationStatus.ESCALATED

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

    def _run_secondary(
        self,
        message: str,
        conversation: ConversationState,
        primary_response: AgentResponse,
        secondary_agent: AgentName,
        handover_reason: str,
    ) -> AgentResponse:
        execute_handover(
            conversation=conversation,
            source_agent=conversation.active_agent,
            target_agent=secondary_agent,
            reason=handover_reason,
            prior_response=primary_response,
        )
        response = self._run_specialist(message, conversation)
        logger.info(
            "secondary_agent_complete",
            extra={
                "trace_id": conversation.trace_id,
                "secondary_agent": secondary_agent,
                "citations": len(response.citations),
            },
        )
        return response

    def _escalate(
        self,
        message: str,
        conversation: ConversationState,
        source_agent: AgentName,
        prior_response: AgentResponse,
        reason: str,
    ) -> AgentResponse:
        execute_handover(
            conversation=conversation,
            source_agent=source_agent,
            target_agent=AgentName.ESCALATION,
            reason=reason,
            prior_response=prior_response,
        )
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