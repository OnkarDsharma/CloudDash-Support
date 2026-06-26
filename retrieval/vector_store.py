import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from retrieval.chunking import ArticleChunk
from retrieval.embeddings_semantic import cosine_similarity, embed as semantic_embed


@dataclass(frozen=True)
class VectorRecord:
    chunk: ArticleChunk
    embedding: list[float]


@dataclass(frozen=True)
class SearchResult:
    chunk: ArticleChunk
    score: float


class JsonVectorStore:
    def __init__(
        self,
        path: str | Path = ".data/vector_store/index.json",
    ) -> None:
        self.path = Path(path)
        self.records: list[VectorRecord] = []


    def build(self, chunks: list[ArticleChunk]) -> None:
        self.records = [
            VectorRecord(
                chunk=chunk,
                embedding=semantic_embed(
                    f"{chunk.title} {' '.join(chunk.tags)} {chunk.text}"
                ),
            )
            for chunk in chunks
        ]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "chunk": asdict(record.chunk),
                "embedding": record.embedding,
            }
            for record in self.records
        ]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.records = [
            VectorRecord(
                chunk=ArticleChunk(**item["chunk"]),
                embedding=item["embedding"],
            )
            for item in payload
        ]

    def search(
        self,
        query: str,
        top_k: int = 4,
        category: str | None = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        query_embedding = semantic_embed(query)
        results: list[SearchResult] = []

        for record in self.records:
            if category and record.chunk.category != category:
                continue
            score = cosine_similarity(query_embedding, record.embedding)
            if score >= min_score:
                results.append(SearchResult(chunk=record.chunk, score=score))

        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def as_metadata(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "record_count": len(self.records),
            "embedding_dimensions": 384,
        }
