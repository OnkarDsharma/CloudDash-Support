from copy import deepcopy

from state.models import ConversationState


class ConversationNotFoundError(Exception):
    def __init__(self, conversation_id: str) -> None:
        super().__init__(f"Conversation not found: {conversation_id}")
        self.conversation_id = conversation_id


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationState] = {}

    def create(self, customer_id: str | None = None) -> ConversationState:
        conversation = ConversationState(customer_id=customer_id)
        self._conversations[conversation.conversation_id] = conversation
        return deepcopy(conversation)

    def get(self, conversation_id: str) -> ConversationState:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return deepcopy(conversation)

    def save(self, conversation: ConversationState) -> ConversationState:
        self._conversations[conversation.conversation_id] = conversation
        return deepcopy(conversation)

    def list(self) -> list[ConversationState]:
        return [deepcopy(conversation) for conversation in self._conversations.values()]


conversation_store = InMemoryConversationStore()
