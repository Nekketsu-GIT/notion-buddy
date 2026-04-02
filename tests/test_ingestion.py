"""Tests for notion_agent.ingestion — IngestionPipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Block flattening
# ---------------------------------------------------------------------------

class TestFlattenBlocks:
    """_flatten_blocks converts raw Notion block responses to plain text."""

    @pytest.mark.asyncio
    async def test_paragraph_block(self, mock_notion_client):
        from notion_agent.ingestion import IngestionPipeline

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._client = mock_notion_client

        text = await pipeline._flatten_blocks("any-page-id")

        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_heading_blocks_are_included(self):
        """heading_1/2/3 blocks must appear in flattened text."""
        from notion_agent.ingestion import IngestionPipeline

        client = MagicMock()
        client.blocks.children.list = AsyncMock(return_value={
            "results": [
                {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Big Title"}]}},
                {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Sub Title"}]}},
                {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Body text."}]}},
            ],
            "has_more": False,
            "next_cursor": None,
        })

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._client = client

        text = await pipeline._flatten_blocks("page-x")

        assert "Big Title" in text
        assert "Sub Title" in text
        assert "Body text." in text

    @pytest.mark.asyncio
    async def test_image_blocks_are_skipped(self):
        """image blocks must be silently ignored (no URL leaks into content)."""
        from notion_agent.ingestion import IngestionPipeline

        client = MagicMock()
        client.blocks.children.list = AsyncMock(return_value={
            "results": [
                {"type": "image", "image": {"type": "external", "external": {"url": "https://example.com/img.png"}}},
                {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Only this."}]}},
            ],
            "has_more": False,
            "next_cursor": None,
        })

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._client = client

        text = await pipeline._flatten_blocks("page-y")

        assert "https://example.com/img.png" not in text
        assert "Only this." in text

    @pytest.mark.asyncio
    async def test_paginated_blocks_are_combined(self):
        """Multiple pages of blocks must all be included in output."""
        from notion_agent.ingestion import IngestionPipeline

        call_count = 0

        async def paginated_list(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "results": [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Page 1 text."}]}}],
                    "has_more": True,
                    "next_cursor": "cursor-abc",
                }
            return {
                "results": [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Page 2 text."}]}}],
                "has_more": False,
                "next_cursor": None,
            }

        client = MagicMock()
        client.blocks.children.list = paginated_list

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._client = client

        text = await pipeline._flatten_blocks("page-z")

        assert "Page 1 text." in text
        assert "Page 2 text." in text


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

class TestChunkAndEmbed:
    def test_short_content_produces_one_chunk(self, sample_notion_page):
        from notion_agent.ingestion import IngestionPipeline
        from notion_agent.models import ChunkedPage

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        # Patch embedding to avoid loading the model
        pipeline._embed = MagicMock(return_value=[[0.0] * 384])

        chunks = pipeline._chunk_and_embed(sample_notion_page)

        assert len(chunks) >= 1
        assert all(isinstance(c, ChunkedPage) for c in chunks)
        assert chunks[0].page_id == sample_notion_page.id

    def test_chunk_ids_are_unique(self, sample_notion_page):
        from notion_agent.ingestion import IngestionPipeline

        # Make content long enough to force multiple chunks
        sample_notion_page.content = ("sentence about Q1 planning decisions.\n" * 200)

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._embed = MagicMock(side_effect=lambda texts: [[0.0] * 384] * len(texts))

        chunks = pipeline._chunk_and_embed(sample_notion_page)
        ids = [c.chunk_id for c in chunks]

        assert len(ids) == len(set(ids)), "chunk_ids must be unique"

    def test_chunk_text_does_not_exceed_token_limit(self, sample_notion_page):
        from notion_agent.ingestion import IngestionPipeline

        sample_notion_page.content = ("word " * 2000)  # ~2000 tokens

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._embed = MagicMock(side_effect=lambda texts: [[0.0] * 384] * len(texts))

        chunks = pipeline._chunk_and_embed(sample_notion_page)

        for chunk in chunks:
            # Rough token count: split on whitespace
            token_count = len(chunk.text.split())
            assert token_count <= 512 + 64, f"chunk exceeded limit: {token_count} tokens"

    def test_embedding_dimension(self, sample_notion_page):
        from notion_agent.ingestion import IngestionPipeline

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._embed = MagicMock(return_value=[[float(i % 10) / 10 for i in range(384)]])

        chunks = pipeline._chunk_and_embed(sample_notion_page)

        assert all(len(c.embedding) == 384 for c in chunks)


# ---------------------------------------------------------------------------
# Skip logic
# ---------------------------------------------------------------------------

class TestSkipLogic:
    @pytest.mark.asyncio
    async def test_unchanged_page_is_skipped(self, sample_notion_page, mock_vector_store):
        """Pages not changed since last index should be skipped (not re-embedded)."""
        from notion_agent.ingestion import IngestionPipeline

        # last_indexed_at returns the same time as last_edited_time → skip
        mock_vector_store.last_indexed_at.return_value = sample_notion_page.last_edited_time

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._vector_store = mock_vector_store
        pipeline._embed = MagicMock()

        should_skip = pipeline._should_skip(sample_notion_page)

        assert should_skip is True
        pipeline._embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_page_is_not_skipped(self, sample_notion_page, mock_vector_store):
        """Pages never indexed before must not be skipped."""
        from notion_agent.ingestion import IngestionPipeline

        mock_vector_store.last_indexed_at.return_value = None  # never indexed

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._vector_store = mock_vector_store

        should_skip = pipeline._should_skip(sample_notion_page)

        assert should_skip is False

    @pytest.mark.asyncio
    async def test_force_reindex_overrides_skip(self, sample_notion_page, mock_vector_store):
        """force_reindex=True must re-embed even unchanged pages."""
        from notion_agent.ingestion import IngestionPipeline

        mock_vector_store.last_indexed_at.return_value = sample_notion_page.last_edited_time

        pipeline = IngestionPipeline.__new__(IngestionPipeline)
        pipeline._vector_store = mock_vector_store
        pipeline._force_reindex = True

        should_skip = pipeline._should_skip(sample_notion_page)

        assert should_skip is False
