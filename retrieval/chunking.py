import re
from dataclasses import dataclass, field
from typing import Any

from knowledge_base.ingest import KnowledgeBaseArticle


@dataclass(frozen=True)
class ArticleChunk:
    chunk_id: str
    source_id: str
    title: str
    category: str
    text: str
    tags: list[str] = field(default_factory=list)
    applies_to: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_article(
    article: KnowledgeBaseArticle,
    max_words: int = 120,
    overlap_words: int = 25,
) -> list[ArticleChunk]:
    words = article.content.split()
    if not words:
        return []

    chunks: list[ArticleChunk] = []
    start = 0
    chunk_index = 1

    while start < len(words):
        end = min(start + max_words, len(words))
        text = " ".join(words[start:end])
        chunks.append(
            ArticleChunk(
                chunk_id=f"{article.id}-{chunk_index:03d}",
                source_id=article.id,
                title=article.title,
                category=article.category,
                text=text,
                tags=article.tags,
                applies_to=article.applies_to,
                metadata={
                    "last_updated": article.last_updated,
                    "chunk_index": chunk_index,
                    "word_start": start,
                    "word_end": end,
                },
            )
        )
        if end == len(words):
            break
        start = max(end - overlap_words, start + 1)
        chunk_index += 1

    return chunks


def chunk_articles(
    articles: list[KnowledgeBaseArticle],
    max_words: int = 120,
    overlap_words: int = 25,
) -> list[ArticleChunk]:
    chunks: list[ArticleChunk] = []
    for article in articles:
        chunks.extend(chunk_article(article, max_words, overlap_words))
    return chunks


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
