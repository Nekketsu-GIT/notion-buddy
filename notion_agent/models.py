"""All dataclasses and shared Notion utilities for the Intelligence Layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# Block types whose text content is extracted during ingestion / tool calls.
# Skipped types: image, video, file, pdf, embed.
SUPPORTED_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "quote",
    "callout",
    "code",
}


def flatten_block_results(results: list[dict]) -> str:
    """Extract plain text from a list of raw Notion block dicts."""
    lines: list[str] = []
    for block in results:
        btype = block.get("type")
        if btype not in SUPPORTED_BLOCK_TYPES:
            continue
        rich_text = block.get(btype, {}).get("rich_text", [])
        text = "".join(rt.get("plain_text", "") for rt in rich_text)
        if text:
            lines.append(text)
    return "\n".join(lines)


def extract_title(properties: dict) -> str:
    """Return the plain-text title from a Notion page's properties dict."""
    for prop in properties.values():
        if prop.get("type") == "title":
            return "".join(t["plain_text"] for t in prop.get("title", []))
    return ""


@dataclass
class NotionPage:
    id: str
    title: str
    url: str
    parent_id: str | None
    last_edited_time: datetime
    created_time: datetime
    created_by: str
    last_edited_by: str
    content: str
    properties: dict
    is_database: bool


@dataclass
class ChunkedPage:
    chunk_id: str
    page_id: str
    page_title: str
    page_url: str
    chunk_index: int
    text: str
    embedding: list[float]
    metadata: dict


@dataclass
class SearchResult:
    page_id: str
    page_title: str
    page_url: str
    chunk_text: str
    score: float
    last_edited_time: datetime
    last_edited_by: str


@dataclass
class AuditEntry:
    page_id: str
    page_title: str
    page_url: str
    owner: str
    last_edited_time: datetime
    days_since_edit: int
    summary: str
    recommendation: str
    status: Literal["stale", "active", "orphaned"]


@dataclass
class AgentResult:
    final_answer: str
    actions_taken: list[str]
    pages_created: list[str]
    duration_seconds: float
    iterations: int
    run_id: str = ""  # set by the agent; use with `python -m notion_agent rollback <run_id>`


@dataclass
class IngestionStats:
    pages_fetched: int
    pages_skipped: int
    chunks_created: int
    duration_seconds: float
