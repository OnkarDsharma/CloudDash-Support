from pydantic import BaseModel

from state.models import ConversationState, Message


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class StartConversationRequest(BaseModel):
    customer_id: str | None = None


class StartConversationResponse(BaseModel):
    conversation_id: str
    trace_id: str
    active_agent: str
    status: str


class SendMessageRequest(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    conversation_id: str
    trace_id: str
    active_agent: str
    customer_message: Message
    assistant_message: Message
    state: ConversationState
