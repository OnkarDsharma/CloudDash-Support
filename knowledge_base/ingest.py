import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.settings import get_settings

if TYPE_CHECKING:
    from retrieval.retriever import KnowledgeBaseRetriever


class KnowledgeBaseArticle(BaseModel):
    id: str
    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    content: str
    last_updated: str
    applies_to: list[str] = Field(default_factory=list)


def load_articles(path: str | Path | None = None) -> list[KnowledgeBaseArticle]:
    settings = get_settings()
    articles_path = Path(path or settings.knowledge_base_path)
    articles: list[KnowledgeBaseArticle] = []

    for article_file in sorted(articles_path.glob("*.json")):
        with article_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
        articles.append(KnowledgeBaseArticle.model_validate(data))

    return articles


def build_retrieval_index(
    articles_path: str | Path | None = None,
    persist: bool = True,
) -> dict[str, int]:
    from retrieval.retriever import KnowledgeBaseRetriever

    retriever: KnowledgeBaseRetriever = KnowledgeBaseRetriever()
    return retriever.build_index(articles_path=articles_path, persist=persist)


if __name__ == "__main__":
    loaded_articles = load_articles()
    print(f"Loaded {len(loaded_articles)} knowledge base articles.")
    index_stats = build_retrieval_index()
    print(f"Built retrieval index with {index_stats['chunks']} chunks.")
