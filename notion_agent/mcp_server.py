"""MCP stdio server exposing 6 Notion tools to the agent."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp import types as mct
from mcp.server import Server
from mcp.server.stdio import stdio_server

from notion_agent.models import extract_title, flatten_block_results


# ---------------------------------------------------------------------------
# Content → Notion blocks conversion
# ---------------------------------------------------------------------------

def _text_block(block_type: str, text: str) -> dict:
    return {
        "type": block_type,
        block_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def content_to_blocks(content: str) -> list[dict]:
    """Convert markdown-ish text to a list of Notion block dicts."""
    blocks: list[dict] = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # Code block
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            blocks.append({
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": lang or "plain text",
                },
            })
            continue

        if line.startswith("### "):
            blocks.append(_text_block("heading_3", line[4:]))
        elif line.startswith("## "):
            blocks.append(_text_block("heading_2", line[3:]))
        elif line.startswith("# "):
            blocks.append(_text_block("heading_1", line[2:]))
        elif re.match(r"^[-*] ", line):
            blocks.append(_text_block("bulleted_list_item", line[2:]))
        elif re.match(r"^\d+\. ", line):
            text = re.sub(r"^\d+\. ", "", line)
            blocks.append(_text_block("numbered_list_item", text))
        elif line.startswith("> "):
            blocks.append(_text_block("quote", line[2:]))
        else:
            blocks.append(_text_block("paragraph", line))

        i += 1

    return blocks


# ---------------------------------------------------------------------------
# Tool handler functions
# ---------------------------------------------------------------------------

async def search_workspace(
    query: str,
    top_k: int = 5,
    filter_stale: bool = False,
    vector_store: Any = None,
) -> list[dict]:
    if not query:
        return []
    results = vector_store.search(query, top_k=top_k)
    if filter_stale:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        results = [r for r in results if r.last_edited_time < cutoff]
    return [
        {
            "page_id": r.page_id,
            "page_title": r.page_title,
            "page_url": r.page_url,
            "chunk_text": r.chunk_text,
            "score": r.score,
            "last_edited_time": r.last_edited_time.isoformat(),
            "last_edited_by": r.last_edited_by,
        }
        for r in results
    ]


async def get_page(page_id: str, notion_client: Any = None) -> dict:
    data = await notion_client.pages.retrieve(page_id=page_id)
    resp = await notion_client.blocks.children.list(block_id=page_id)
    props = data.get("properties", {})
    return {
        "id": data["id"],
        "title": extract_title(props),
        "url": data.get("url", ""),
        "content": flatten_block_results(resp.get("results", [])),
        "properties": props,
        "last_edited_time": data.get("last_edited_time", ""),
        "last_edited_by": data.get("last_edited_by", {}).get("name", ""),
    }


async def list_database_entries(
    database_id: str,
    filter: dict | None = None,
    notion_client: Any = None,
) -> list[dict]:
    kwargs: dict = {"database_id": database_id}
    if filter:
        kwargs["filter"] = filter
    resp = await notion_client.databases.query(**kwargs)
    return [{"id": r["id"], "properties": r.get("properties", {})} for r in resp.get("results", [])]


async def create_page(
    parent_id: str,
    parent_type: str,
    title: str,
    content: str,
    properties: dict | None = None,
    notion_client: Any = None,
) -> dict:
    parent = {"database_id": parent_id} if parent_type == "database" else {"page_id": parent_id}
    title_prop = {"title": [{"type": "text", "text": {"content": title}}]}
    result = await notion_client.pages.create(
        parent=parent,
        properties={"title": title_prop, **(properties or {})},
        children=content_to_blocks(content),
    )
    return {"page_id": result["id"], "url": result["url"]}


async def append_blocks(page_id: str, content: str, notion_client: Any = None) -> dict:
    await notion_client.blocks.children.append(
        block_id=page_id, children=content_to_blocks(content)
    )
    return {"success": True}


async def update_page_property(
    page_id: str,
    property_name: str,
    value: Any,
    notion_client: Any = None,
) -> dict:
    await notion_client.pages.update(
        page_id=page_id,
        properties={
            property_name: {
                "rich_text": [{"type": "text", "text": {"content": str(value)}}]
            }
        },
    )
    return {"success": True}


# ---------------------------------------------------------------------------
# MCP server entrypoint (stdio transport)
# ---------------------------------------------------------------------------

def run_server() -> None:
    """Start the MCP stdio server."""
    import asyncio

    from notion_agent.config import get_settings
    from notion_agent.vector_store import VectorStore
    from notion_client import AsyncClient

    settings = get_settings()
    notion = AsyncClient(auth=settings.notion_api_key)
    store = VectorStore(persist_dir=settings.chroma_persist_dir)

    server = Server("notion-agent")

    @server.list_tools()
    async def _list_tools() -> list[mct.Tool]:
        return [
            mct.Tool(name="search_workspace", description="Semantic search over indexed Notion pages.",
                     inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}, "filter_stale": {"type": "boolean", "default": False}}, "required": ["query"]}),
            mct.Tool(name="get_page", description="Fetch full content and metadata of a Notion page.",
                     inputSchema={"type": "object", "properties": {"page_id": {"type": "string"}}, "required": ["page_id"]}),
            mct.Tool(name="list_database_entries", description="List all entries in a Notion database.",
                     inputSchema={"type": "object", "properties": {"database_id": {"type": "string"}, "filter": {"type": "object"}}, "required": ["database_id"]}),
            mct.Tool(name="create_page", description="Create a new Notion page or database entry.",
                     inputSchema={"type": "object", "properties": {"parent_id": {"type": "string"}, "parent_type": {"type": "string", "enum": ["page", "database"]}, "title": {"type": "string"}, "content": {"type": "string"}, "properties": {"type": "object"}}, "required": ["parent_id", "parent_type", "title", "content"]}),
            mct.Tool(name="append_blocks", description="Append content blocks to an existing Notion page.",
                     inputSchema={"type": "object", "properties": {"page_id": {"type": "string"}, "content": {"type": "string"}}, "required": ["page_id", "content"]}),
            mct.Tool(name="update_page_property", description="Update a single property on a Notion database entry.",
                     inputSchema={"type": "object", "properties": {"page_id": {"type": "string"}, "property_name": {"type": "string"}, "value": {}}, "required": ["page_id", "property_name", "value"]}),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[mct.TextContent]:
        handlers = {
            "search_workspace": lambda: search_workspace(vector_store=store, **arguments),
            "get_page": lambda: get_page(notion_client=notion, **arguments),
            "list_database_entries": lambda: list_database_entries(notion_client=notion, **arguments),
            "create_page": lambda: create_page(notion_client=notion, **arguments),
            "append_blocks": lambda: append_blocks(notion_client=notion, **arguments),
            "update_page_property": lambda: update_page_property(notion_client=notion, **arguments),
        }
        handler = handlers.get(name)
        if handler is None:
            raise ValueError(f"Unknown tool: {name}")
        result = await handler()
        return [mct.TextContent(type="text", text=json.dumps(result, default=str))]

    asyncio.run(stdio_server(server))
