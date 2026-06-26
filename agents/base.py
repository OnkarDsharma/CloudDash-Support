from abc import ABC, abstractmethod

from retrieval.retriever import KnowledgeBaseRetriever
from state.models import AgentName, AgentResponse, ConversationState


class BaseAgent(ABC):
    name: AgentName

    def __init__(self, retriever: KnowledgeBaseRetriever | None = None) -> None:
        self.retriever = retriever or KnowledgeBaseRetriever()

    @abstractmethod
    def run(self, message: str, conversation: ConversationState) -> AgentResponse:
        raise NotImplementedError


def format_citations(response: AgentResponse) -> str:
    if not response.citations:
        return ""

    seen: set[str] = set()
    source_labels: list[str] = []
    for citation in response.citations:
        if citation.source_id in seen:
            continue
        seen.add(citation.source_id)
        source_labels.append(f"{citation.source_id} - {citation.title}")

    return " Sources: " + "; ".join(source_labels)
