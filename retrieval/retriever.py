from pathlib import Path

from knowledge_base.ingest import load_articles
from retrieval.chunking import chunk_articles, normalize_text
from retrieval.vector_store import JsonVectorStore
from state.models import ConversationState, MessageRole, RetrievalResult


class KnowledgeBaseRetriever:
    def __init__(self, vector_store: JsonVectorStore | None = None) -> None:
        self.vector_store = vector_store or JsonVectorStore()
        self._is_ready = False

    def build_index(
        self,
        articles_path: str | Path | None = None,
        persist: bool = True,
    ) -> dict[str, int]:
        articles = load_articles(articles_path)
        chunks = chunk_articles(articles)
        self.vector_store.build(chunks)
        if persist:
            self.vector_store.save()
        self._is_ready = True
        return {
            "articles": len(articles),
            "chunks": len(chunks),
        }

    def load_index(self) -> None:
        self.vector_store.load()
        self._is_ready = True

    def retrieve(
        self,
        query: str,
        conversation: ConversationState | None = None,
        top_k: int = 4,
        category: str | None = None,
        min_score: float = 0.05,
    ) -> list[RetrievalResult]:
        self.ensure_ready()
        rewritten_query = rewrite_query(query, conversation)
        search_results = self.vector_store.search(
            rewritten_query,
            top_k=top_k,
            category=category,
            min_score=min_score,
        )

        return [
            RetrievalResult(
                source_id=result.chunk.source_id,
                title=result.chunk.title,
                category=result.chunk.category,
                snippet=normalize_text(result.chunk.text),
                score=round(result.score, 4),
                metadata={
                    "chunk_id": result.chunk.chunk_id,
                    "tags": result.chunk.tags,
                    "applies_to": result.chunk.applies_to,
                    **result.chunk.metadata,
                },
            )
            for result in search_results
        ]

    def ensure_ready(self) -> None:
        if self._is_ready:
            return
        if self.vector_store.path.exists():
            self.load_index()
            return
        self.build_index(persist=True)


def rewrite_query(
    query: str,
    conversation: ConversationState | None = None,
    max_messages: int = 4,
) -> str:
    if conversation is None:
        return query

    context_parts: list[str] = []
    if conversation.summary:
        context_parts.append(conversation.summary)
    if conversation.current_intent:
        context_parts.append(f"intent: {conversation.current_intent}")
    if conversation.entities:
        entity_text = " ".join(f"{key}: {value}" for key, value in conversation.entities.items())
        context_parts.append(entity_text)

    recent_customer_messages = [
        message.content
        for message in conversation.messages
        if message.role == MessageRole.CUSTOMER
    ][-max_messages:]
    context_parts.extend(recent_customer_messages)
    context_parts.append(query)

    return " ".join(part for part in context_parts if part)
