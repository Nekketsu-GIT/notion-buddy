"""Shared fixtures for all test modules."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _page_id() -> str:
    return str(uuid.uuid4()).replace("-", "")


# ---------------------------------------------------------------------------
# Model fixtures  (imported lazily so tests can run before notion_agent exists)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_page_id() -> str:
    return "abc123def456abc123def456abc12345"


@pytest.fixture()
def sample_notion_page(sample_page_id):
    """A realistic NotionPage for use across tests."""
    from notion_agent.models import NotionPage

    return NotionPage(
        id=sample_page_id,
        title="Q1 Planning — Engineering",
        url=f"https://www.notion.so/Q1-Planning-Engineering-{sample_page_id}",
        parent_id=None,
        last_edited_time=_utc(2026, 3, 1),
        created_time=_utc(2026, 1, 10),
        created_by="Alice",
        last_edited_by="Alice",
        content=(
            "This page captures all engineering decisions for Q1 2026.\n"
            "Key outcomes: adopt async ingestion, ship MCP server by Feb 28.\n"
            "Owner: Alice. Status: active."
        ),
        properties={},
        is_database=False,
    )


@pytest.fixture()
def stale_notion_page():
    """A page last edited more than 30 days before the test freeze date (2026-04-02)."""
    from notion_agent.models import NotionPage

    pid = _page_id()
    return NotionPage(
        id=pid,
        title="Team Norms (old)",
        url=f"https://www.notion.so/Team-Norms-{pid}",
        parent_id=None,
        last_edited_time=_utc(2026, 1, 15),   # 77 days before 2026-04-02
        created_time=_utc(2025, 11, 1),
        created_by="Bob",
        last_edited_by="Bob",
        content="These are our team norms. Work in progress.",
        properties={},
        is_database=False,
    )


@pytest.fixture()
def sample_chunked_page(sample_notion_page):
    """A single ChunkedPage derived from sample_notion_page."""
    from notion_agent.models import ChunkedPage

    return ChunkedPage(
        chunk_id=f"{sample_notion_page.id}_0",
        page_id=sample_notion_page.id,
        page_title=sample_notion_page.title,
        page_url=sample_notion_page.url,
        chunk_index=0,
        text=sample_notion_page.content,
        embedding=[0.1] * 384,   # dummy 384-dim vector
        metadata={
            "last_edited_time": sample_notion_page.last_edited_time.isoformat(),
            "created_by": sample_notion_page.created_by,
            "last_edited_by": sample_notion_page.last_edited_by,
            "is_database": False,
        },
    )


@pytest.fixture()
def sample_search_result(sample_page_id):
    """A SearchResult pointing at the sample page."""
    from notion_agent.models import SearchResult

    return SearchResult(
        page_id=sample_page_id,
        page_title="Q1 Planning — Engineering",
        page_url=f"https://www.notion.so/Q1-Planning-Engineering-{sample_page_id}",
        chunk_text="Key outcomes: adopt async ingestion, ship MCP server by Feb 28.",
        score=0.82,
        last_edited_time=_utc(2026, 3, 1),
        last_edited_by="Alice",
    )


# ---------------------------------------------------------------------------
# Mock Notion client
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_notion_client(sample_notion_page):
    """AsyncMock of notion_client.AsyncClient wired to return sample data."""
    client = MagicMock()

    # pages.retrieve
    client.pages.retrieve = AsyncMock(return_value={
        "id": sample_notion_page.id,
        "url": sample_notion_page.url,
        "parent": {"type": "workspace", "workspace": True},
        "last_edited_time": sample_notion_page.last_edited_time.isoformat(),
        "created_time": sample_notion_page.created_time.isoformat(),
        "created_by": {"object": "user", "id": "user1", "name": "Alice"},
        "last_edited_by": {"object": "user", "id": "user1", "name": "Alice"},
        "properties": {
            "title": {
                "type": "title",
                "title": [{"plain_text": sample_notion_page.title}],
            }
        },
        "is_database": False,
    })

    # blocks.children.list — returns one paragraph block
    client.blocks.children.list = AsyncMock(return_value={
        "results": [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": sample_notion_page.content}]
                },
            }
        ],
        "has_more": False,
        "next_cursor": None,
    })

    # search — returns one page
    client.search = AsyncMock(return_value={
        "results": [
            {
                "object": "page",
                "id": sample_notion_page.id,
                "url": sample_notion_page.url,
                "parent": {"type": "workspace", "workspace": True},
                "last_edited_time": sample_notion_page.last_edited_time.isoformat(),
                "created_time": sample_notion_page.created_time.isoformat(),
                "created_by": {"object": "user", "id": "user1", "name": "Alice"},
                "last_edited_by": {"object": "user", "id": "user1", "name": "Alice"},
                "properties": {
                    "title": {
                        "type": "title",
                        "title": [{"plain_text": sample_notion_page.title}],
                    }
                },
            }
        ],
        "has_more": False,
        "next_cursor": None,
    })

    # pages.create
    new_id = _page_id()
    client.pages.create = AsyncMock(return_value={
        "id": new_id,
        "url": f"https://www.notion.so/New-Page-{new_id}",
    })

    # blocks.children.append
    client.blocks.children.append = AsyncMock(return_value={"results": []})

    # pages.update
    client.pages.update = AsyncMock(return_value={"id": sample_notion_page.id})

    return client


# ---------------------------------------------------------------------------
# Mock VectorStore
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_vector_store(sample_search_result):
    """MagicMock of VectorStore returning a single search result."""
    store = MagicMock()
    store.search.return_value = [sample_search_result]
    store.upsert.return_value = None
    store.delete_page.return_value = None
    store.count.return_value = 1
    store.last_indexed_at.return_value = None
    return store


# ---------------------------------------------------------------------------
# Pytest-asyncio mode
# ---------------------------------------------------------------------------

# Tell pytest-asyncio to use "auto" mode so async test functions don't need
# the @pytest.mark.asyncio decorator on every single test.
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async (handled by pytest-asyncio)",
    )
