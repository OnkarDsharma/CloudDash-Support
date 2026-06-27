"""
retrieval/embeddings_semantic.py

Semantic embedder using sentence-transformers.
Model is loaded at import time so it's ready before the first API request.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

# Load once at import time — avoids timeout on first request in production
_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> list[float]:
    return _model.encode(text, normalize_embeddings=True).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom else 0.0