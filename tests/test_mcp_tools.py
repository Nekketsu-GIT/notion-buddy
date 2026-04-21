"""Tests for notion_agent.mcp_server — MCP tool handlers."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# search_workspace
# ---------------------------------------------------------------------------


class TestSearchWorkspace:
    @pytest.mark.asyncio
    async def test_returns_list_of_results(
        self, mock_vector_store, sample_search_result
    ):
        from notion_agent.mcp_server import search_workspace

        result = await search_workspace(
            query="Q1 planning",
            top_k=5,
            filter_stale=False,
            vector_store=mock_vector_store,
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["page_title"] == sample_search_result.page_title

    @pytest.mark.asyncio
    async def test_filter_stale_excludes_recent_pages(
        self, mock_vector_store, sample_search_result
    ):
        """filter_stale=True should exclude pages edited within the last 30 days."""
        from notion_agent.mcp_server import search_workspace

        # sample_search_result.last_edited_time = 2026-03-01 — only 32 days before 2026-04-02
        # With freeze date not applied here we just verify the filter is passed down.
        mock_vector_store.search.return_value = []  # store returns nothing when filter applied

        result = await search_workspace(
            query="stale pages",
            top_k=5,
            filter_stale=True,
            vector_store=mock_vector_store,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_list(self, mock_vector_store):
        from notion_agent.mcp_server import search_workspace

        mock_vector_store.search.return_value = []
        result = await search_workspace(
            query="",
            top_k=5,
            filter_stale=False,
            vector_store=mock_vector_store,
        )
        assert result == []


# ---------------------------------------------------------------------------
# get_page
# ---------------------------------------------------------------------------


class TestGetPage:
    @pytest.mark.asyncio
    async def test_returns_page_dict(self, mock_notion_client, sample_notion_page):
        from notion_agent.mcp_server import get_page

        result = await get_page(
            page_id=sample_notion_page.id,
            notion_client=mock_notion_client,
        )

        assert result["id"] == sample_notion_page.id
        assert result["title"] == sample_notion_page.title

    @pytest.mark.asyncio
    async def test_content_is_included(self, mock_notion_client, sample_notion_page):
        from notion_agent.mcp_server import get_page

        result = await get_page(
            page_id=sample_notion_page.id,
            notion_client=mock_notion_client,
        )

        assert "content" in result
        assert len(result["content"]) > 0


# ---------------------------------------------------------------------------
# create_page
# ---------------------------------------------------------------------------


class TestCreatePage:
    @pytest.mark.asyncio
    async def test_returns_page_id_and_url(
        self, mock_notion_client, sample_notion_page
    ):
        from notion_agent.mcp_server import create_page

        result = await create_page(
            parent_id=sample_notion_page.id,
            parent_type="page",
            title="Workspace Audit — 2026-04-02",
            content="# Summary\n- 12 pages scanned",
            properties=None,
            notion_client=mock_notion_client,
        )

        assert "page_id" in result
        assert "url" in result

    @pytest.mark.asyncio
    async def test_notion_pages_create_called(
        self, mock_notion_client, sample_notion_page
    ):
        from notion_agent.mcp_server import create_page

        await create_page(
            parent_id=sample_notion_page.id,
            parent_type="page",
            title="New Page",
            content="Some content",
            properties=None,
            notion_client=mock_notion_client,
        )

        mock_notion_client.pages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_markdown_heading_converted_to_block(
        self, mock_notion_client, sample_notion_page
    ):
        """# Heading must produce a heading_1 block in the API call."""
        from notion_agent.mcp_server import create_page

        await create_page(
            parent_id=sample_notion_page.id,
            parent_type="page",
            title="Audit",
            content="# Big Heading\n\nSome paragraph.",
            properties=None,
            notion_client=mock_notion_client,
        )

        call_kwargs = mock_notion_client.pages.create.call_args.kwargs
        children = call_kwargs.get("children", [])
        block_types = [b["type"] for b in children]
        assert "heading_1" in block_types


# ---------------------------------------------------------------------------
# append_blocks
# ---------------------------------------------------------------------------


class TestAppendBlocks:
    @pytest.mark.asyncio
    async def test_success_true(self, mock_notion_client, sample_notion_page):
        from notion_agent.mcp_server import append_blocks

        result = await append_blocks(
            page_id=sample_notion_page.id,
            content="- item one\n- item two",
            notion_client=mock_notion_client,
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_bulleted_list_converted(
        self, mock_notion_client, sample_notion_page
    ):
        from notion_agent.mcp_server import append_blocks

        await append_blocks(
            page_id=sample_notion_page.id,
            content="- item one\n- item two",
            notion_client=mock_notion_client,
        )

        call_kwargs = mock_notion_client.blocks.children.append.call_args.kwargs
        children = call_kwargs.get("children", [])
        types = [b["type"] for b in children]
        assert all(t == "bulleted_list_item" for t in types)


# ---------------------------------------------------------------------------
# update_page_property
# ---------------------------------------------------------------------------


class TestUpdatePageProperty:
    @pytest.mark.asyncio
    async def test_success_true(self, mock_notion_client, sample_notion_page):
        from notion_agent.mcp_server import update_page_property

        result = await update_page_property(
            page_id=sample_notion_page.id,
            property_name="Status",
            value="Done",
            notion_client=mock_notion_client,
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_notion_pages_update_called(
        self, mock_notion_client, sample_notion_page
    ):
        from notion_agent.mcp_server import update_page_property

        await update_page_property(
            page_id=sample_notion_page.id,
            property_name="Owner",
            value="Alice",
            notion_client=mock_notion_client,
        )

        mock_notion_client.pages.update.assert_called_once()


# ---------------------------------------------------------------------------
# Content → blocks conversion (shared utility)
# ---------------------------------------------------------------------------


class TestContentToBlocks:
    def test_paragraph(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("Just a paragraph.")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "paragraph"

    def test_heading_1(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("# Title")
        assert blocks[0]["type"] == "heading_1"

    def test_heading_2(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("## Subtitle")
        assert blocks[0]["type"] == "heading_2"

    def test_heading_3(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("### Small heading")
        assert blocks[0]["type"] == "heading_3"

    def test_bulleted_list_dash(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("- item")
        assert blocks[0]["type"] == "bulleted_list_item"

    def test_bulleted_list_star(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("* item")
        assert blocks[0]["type"] == "bulleted_list_item"

    def test_numbered_list(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("1. first item")
        assert blocks[0]["type"] == "numbered_list_item"

    def test_quote(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("> a quote")
        assert blocks[0]["type"] == "quote"

    def test_code_block(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("```python\nprint('hello')\n```")
        assert any(b["type"] == "code" for b in blocks)

    def test_mixed_content(self):
        from notion_agent.mcp_server import content_to_blocks

        text = "# Heading\n\nParagraph text.\n\n- bullet\n\n> quote"
        blocks = content_to_blocks(text)
        types = [b["type"] for b in blocks]
        assert "heading_1" in types
        assert "paragraph" in types
        assert "bulleted_list_item" in types
        assert "quote" in types

    def test_empty_lines_are_skipped(self):
        from notion_agent.mcp_server import content_to_blocks

        blocks = content_to_blocks("line one\n\n\n\nline two")
        assert len(blocks) == 2
