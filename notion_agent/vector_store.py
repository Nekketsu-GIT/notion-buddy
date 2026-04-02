"""VectorStore: ChromaDB wrapper with search, upsert, and delete."""

from __future__ import annotations

from datetime import datetime

import chromadb

from notion_agent.models import ChunkedPage, SearchResult

_COLLECTION_NAME = "notion_pages"
_SCORE_THRESHOLD = 0.3
_embedding_model = None


def get_embedding_model():
    """Return the shared SentenceTransformer instance, loading it on first call."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedding_model


class VectorStore:
    def __init__(self, persist_dir: str = "./.chroma"):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed_query(self, query: str) -> list[float]:
        return get_embedding_model().encode(query).tolist()

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        embedding = self._embed_query(query)
        raw = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        results: list[SearchResult] = []
        for doc, dist, meta in zip(
            raw["documents"][0],
            raw["distances"][0],
            raw["metadatas"][0],
        ):
            score = 1.0 - dist
            if score < _SCORE_THRESHOLD:
                continue
            results.append(
                SearchResult(
                    page_id=meta["page_id"],
                    page_title=meta["page_title"],
                    page_url=meta["page_url"],
                    chunk_text=doc,
                    score=score,
                    last_edited_time=datetime.fromisoformat(meta["last_edited_time"]),
                    last_edited_by=meta["last_edited_by"],
                )
            )
        return results

    def upsert(self, chunks: list[ChunkedPage]) -> None:
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=[c.embedding for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {"page_id": c.page_id, "page_title": c.page_title, "page_url": c.page_url, **c.metadata}
                for c in chunks
            ],
        )

    def delete_page(self, page_id: str) -> None:
        self._collection.delete(where={"page_id": page_id})

    def count(self) -> int:
        return self._collection.count()

    def last_indexed_at(self, page_id: str) -> datetime | None:
        result = self._collection.get(
            where={"page_id": page_id},
            include=["metadatas"],
            limit=1,
        )
        if not result["ids"]:
            return None
        return datetime.fromisoformat(result["metadatas"][0]["last_edited_time"])
