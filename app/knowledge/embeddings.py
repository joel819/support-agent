"""Local embeddings. No paid APIs.

- SentenceTransformerEmbedder: all-MiniLM-L6-v2 (384-dim), downloaded once (~90 MB).
- HashEmbedder: deterministic feature-hashing embedder for tests and fully offline use.
  Keyword-level only, so answers are weaker, but it needs no model download.
"""
import hashlib
import math
from collections import Counter
from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.knowledge.text import keywords

DIM = 384


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # heavy import, load lazily

        self.name = model_name
        self.model = SentenceTransformer(model_name, device="cpu")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vecs = self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()


class HashEmbedder:
    name = "hash"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    @staticmethod
    def _one(text: str) -> list[float]:
        vec = [0.0] * DIM
        for tok, count in Counter(keywords(text)).items():
            weight = 1.0 + math.log(count)  # sublinear term frequency
            # Two signed slots per token: a single collision can no longer cancel a word out.
            digest = hashlib.blake2b(tok.encode(), digest_size=16).digest()
            for h in (int.from_bytes(digest[:8], "big"), int.from_bytes(digest[8:], "big")):
                vec[h % DIM] += weight if (h >> 32) & 1 else -weight
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_backend == "hash":
        return HashEmbedder()
    return SentenceTransformerEmbedder(s.embedding_model)
