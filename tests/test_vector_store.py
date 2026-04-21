"""Tests for notion_agent.vector_store — VectorStore (ChromaDB wrapper)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chroma_query_result(page_id: str, chunk_text: str, score: float):
    """Build the dict shape that chromadb returns from collection.query()."""
    chunk_id = f"{page_id}_0"
    return {
        "ids": [[chunk_id]],
        "documents": [[chunk_text]],
        "distances": [[1.0 - score]],   # chromadb stores L2 / cosine distance
        "metadatas": [[{
            "page_id": page_id,
            "page_title": "Q1 Planning",
            "page_url": f"https://www.notion.so/{page_id}",
            "last_edited_time": "2026-03-01T00:00:00+00:00",
            "last_edited_by": "Alice",
            "is_database": False,
        }]],
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestVectorStoreSearch:
    def test_returns_search_results_above_threshold(self, sample_chunked_page):
        from notion_agent.vector_store import VectorStore
        from notion_agent.models import SearchResult

        mock_collection = MagicMock()
        mock_collection.query.return_value = _make_chroma_query_result(
            sample_chunked_page.page_id,
            sample_chunked_page.text,
            score=0.75,
        )

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            store._embed_query = MagicMock(return_value=[0.1] * 384)

            results = store.search("Q1 planning decisions", top_k=5)

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].score >= 0.3

    def test_filters_low_score_results(self, sample_chunked_page):
        """Results below 0.3 cosine similarity must be excluded."""
        from notion_agent.vector_store import VectorStore

        mock_collection = MagicMock()
        mock_collection.query.return_value = _make_chroma_query_result(
            sample_chunked_page.page_id,
            sample_chunked_page.text,
            score=0.1,   # below threshold
        )

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            store._embed_query = MagicMock(return_value=[0.1] * 384)

            results = store.search("irrelevant query", top_k=5)

        assert results == []

    def test_top_k_is_passed_to_chroma(self, sample_chunked_page):
        from notion_agent.vector_store import VectorStore

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]
        }

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            store._embed_query = MagicMock(return_value=[0.1] * 384)

            store.search("anything", top_k=3)

        call_kwargs = mock_collection.query.call_args
        assert call_kwargs.kwargs.get("n_results") == 3 or call_kwargs.args[0] == 3


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

class TestVectorStoreUpsert:
    def test_upsert_calls_collection_upsert(self, sample_chunked_page):
        from notion_agent.vector_store import VectorStore

        mock_collection = MagicMock()

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            store.upsert([sample_chunked_page])

        mock_collection.upsert.assert_called_once()

    def test_upsert_passes_correct_ids(self, sample_chunked_page):
        from notion_agent.vector_store import VectorStore

        mock_collection = MagicMock()

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            store.upsert([sample_chunked_page])

        call_kwargs = mock_collection.upsert.call_args
        ids = call_kwargs.kwargs.get("ids") or call_kwargs.args[0]
        assert sample_chunked_page.chunk_id in ids


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestVectorStoreDelete:
    def test_delete_page_removes_all_chunks(self, sample_chunked_page):
        from notion_agent.vector_store import VectorStore

        mock_collection = MagicMock()
        # Simulate get() returning one matching chunk
        mock_collection.get.return_value = {
            "ids": [sample_chunked_page.chunk_id],
        }

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            store.delete_page(sample_chunked_page.page_id)

        mock_collection.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Count / last_indexed_at
# ---------------------------------------------------------------------------

class TestVectorStoreMetadata:
    def test_count_returns_integer(self):
        from notion_agent.vector_store import VectorStore

        mock_collection = MagicMock()
        mock_collection.count.return_value = 42

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            result = store.count()

        assert result == 42

    def test_last_indexed_at_returns_none_for_unknown_page(self):
        from notion_agent.vector_store import VectorStore

        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": [], "metadatas": []}

        with patch("notion_agent.vector_store.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection
            store = VectorStore(persist_dir="./.chroma_test")
            result = store.last_indexed_at("unknown-page-id")

        assert result is None
