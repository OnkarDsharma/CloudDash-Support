"""
api/routes.py

Thin HTTP layer. All agent/orchestration logic lives in agents/orchestrator.py.
Guardrails are applied here — before the orchestrator (input) and before
returning the response (output).
"""

import logging

from fastapi import APIRouter, HTTPException, status

from agents.orchestrator import Orchestrator
from api.schemas import (
    HealthResponse,
    SendMessageRequest,
    SendMessageResponse,
    StartConversationRequest,
    StartConversationResponse,
)
from services.guardrails import check_input, check_output
from services.settings import get_settings
from state.models import AgentName, Message, MessageRole
from state.store import ConversationNotFoundError, conversation_store

logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = Orchestrator()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.post(
    "/conversations",
    response_model=StartConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_conversation(request: StartConversationRequest) -> StartConversationResponse:
    conversation = conversation_store.create(customer_id=request.customer_id)
    return StartConversationResponse(
        conversation_id=conversation.conversation_id,
        trace_id=conversation.trace_id,
        active_agent=conversation.active_agent,
        status=conversation.status,
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    try:
        return conversation_store.get(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
)
def send_message(conversation_id: str, request: SendMessageRequest) -> SendMessageResponse:
    try:
        conversation = conversation_store.get(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # 1. INPUT GUARDRAIL
    input_check = check_input(request.content)

    customer_message = Message(role=MessageRole.CUSTOMER, content=request.content)
    conversation.add_message(customer_message)

    if not input_check.safe:
        # Short-circuit: log, store a safe assistant reply, skip orchestrator
        logger.warning(
            "input_blocked",
            extra={
                "trace_id": conversation.trace_id,
                "reason": input_check.reason,
            },
        )
        assistant_message = Message(
            role=MessageRole.ASSISTANT,
            agent=AgentName.TRIAGE,
            content=input_check.sanitized_content,
        )
        conversation.add_message(assistant_message)
        conversation_store.save(conversation)
        return SendMessageResponse(
            conversation_id=conversation.conversation_id,
            trace_id=conversation.trace_id,
            active_agent=conversation.active_agent,
            customer_message=customer_message,
            assistant_message=assistant_message,
            state=conversation,
        )

    # 2. ORCHESTRATE (triage -> specialist -> optional escalation)
    agent_response = orchestrator.handle(request.content, conversation)

    # 3. OUTPUT GUARDRAIL
    output_check = check_output(
        content=agent_response.content,
        citations=agent_response.citations,
        original_message=request.content,
    )
    safe_content = output_check.content

    # 4. Append assistant message with guardrail-sanitized content
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        agent=agent_response.agent,
        content=safe_content,
        citations=agent_response.citations,
    )
    conversation.add_message(assistant_message)

    # 5. Persist
    conversation_store.save(conversation)

    return SendMessageResponse(
        conversation_id=conversation.conversation_id,
        trace_id=conversation.trace_id,
        active_agent=conversation.active_agent,
        customer_message=customer_message,
        assistant_message=assistant_message,
        state=conversation,
    )