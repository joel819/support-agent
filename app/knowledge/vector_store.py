"""ChromaDB persistent store for policy sections. We pass our own embeddings,
so Chroma never downloads its default embedding model."""
from dataclasses import dataclass
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.knowledge.embeddings import get_embedder
from app.knowledge.loader import Section

COLLECTION = "policy_sections"


@dataclass
class PolicyHit:
    section_id: str
    title: str
    text: str
    score: float  # cosine similarity


class PolicyStore:
    def __init__(self, path: str):
        self.client = chromadb.PersistentClient(path=path, settings=ChromaSettings(anonymized_telemetry=False))
        self.collection = self._collection()

    def _collection(self):
        return self.client.get_or_create_collection(
            COLLECTION, embedding_function=None, metadata={"hnsw:space": "cosine"}
        )

    def index(self, sections: list[Section]) -> int:
        """Replace the whole index with these sections (policy is small; rebuild is instant)."""
        self.reset()
        if not sections:
            return 0
        # Embed title + body so headings like "Returns" help retrieval.
        vecs = get_embedder().embed([f"{s.title}. {s.text}" for s in sections])
        self.collection.add(
            ids=[s.id for s in sections],
            embeddings=vecs,
            documents=[s.text for s in sections],
            metadatas=[{"title": s.title} for s in sections],
        )
        return len(sections)

    def search(self, query: str, k: int) -> list[PolicyHit]:
        total = self.collection.count()
        if total == 0:
            return []
        [vec] = get_embedder().embed([query])
        res = self.collection.query(
            query_embeddings=[vec], n_results=min(k, total), include=["documents", "metadatas", "distances"]
        )
        return [
            PolicyHit(section_id=i, title=m["title"], text=d, score=1.0 - dist)
            for i, d, m, dist in zip(
                res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True
            )
        ]

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        self.client.delete_collection(COLLECTION)
        self.collection = self._collection()


@lru_cache
def get_policy_store() -> PolicyStore:
    path = get_settings().chroma_dir
    path.mkdir(parents=True, exist_ok=True)
    return PolicyStore(str(path))
