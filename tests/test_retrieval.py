from pathlib import Path

from knowledge_base.ingest import load_articles
from retrieval.chunking import chunk_articles
from retrieval.retriever import KnowledgeBaseRetriever, rewrite_query
from retrieval.vector_store import JsonVectorStore
from state.models import ConversationState, Message, MessageRole


def make_retriever(tmp_path: Path) -> KnowledgeBaseRetriever:
    store = JsonVectorStore(path=tmp_path / "index.json")
    retriever = KnowledgeBaseRetriever(vector_store=store)
    retriever.build_index(persist=True)
    return retriever


def test_chunks_articles() -> None:
    articles = load_articles()
    chunks = chunk_articles(articles, max_words=60, overlap_words=10)

    assert len(chunks) >= len(articles)
    assert all(chunk.chunk_id.startswith(chunk.source_id) for chunk in chunks)
    assert all(chunk.text for chunk in chunks)


def test_builds_and_loads_vector_index(tmp_path: Path) -> None:
    retriever = make_retriever(tmp_path)
    index_path = tmp_path / "index.json"

    assert index_path.exists()
    assert retriever.vector_store.as_metadata()["record_count"] > 0

    loaded = KnowledgeBaseRetriever(vector_store=JsonVectorStore(path=index_path))
    loaded.load_index()

    assert loaded.vector_store.as_metadata()["record_count"] == retriever.vector_store.as_metadata()["record_count"]


def test_retrieves_aws_alert_failure_article(tmp_path: Path) -> None:
    retriever = make_retriever(tmp_path)

    results = retriever.retrieve(
        "My CloudDash alerts stopped firing after I updated AWS credentials yesterday.",
        top_k=3,
    )

    assert results
    assert results[0].source_id == "KB-005"
    assert "AWS Credentials" in results[0].title


def test_retrieves_duplicate_charge_escalation_policy(tmp_path: Path) -> None:
    retriever = make_retriever(tmp_path)

    results = retriever.retrieve(
        "I was charged twice for April and need an immediate refund and a manager.",
        top_k=3,
    )

    source_ids = {result.source_id for result in results}
    assert "KB-017" in source_ids


def test_category_filter_limits_results(tmp_path: Path) -> None:
    retriever = make_retriever(tmp_path)

    results = retriever.retrieve(
        "How do I authenticate to the API?",
        category="api_documentation",
    )

    assert results
    assert all(result.category == "api_documentation" for result in results)


def test_rewrite_query_uses_conversation_context() -> None:
    conversation = ConversationState(
        summary="Customer is troubleshooting CloudDash AWS integration.",
        current_intent="technical_issue",
        entities={"plan": "Pro", "cloud_provider": "AWS"},
    )
    conversation.add_message(
        Message(
            role=MessageRole.CUSTOMER,
            content="My alerts stopped firing yesterday.",
        )
    )

    rewritten = rewrite_query("What should I check next?", conversation)

    assert "technical_issue" in rewritten
    assert "AWS" in rewritten
    assert "alerts stopped firing" in rewritten
    assert "What should I check next?" in rewritten
