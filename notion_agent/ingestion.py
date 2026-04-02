"""IngestionPipeline: fetch Notion pages, flatten, chunk, embed, store."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

from notion_client import AsyncClient

from notion_agent.config import get_settings
from notion_agent.models import (
    ChunkedPage,
    IngestionStats,
    NotionPage,
    extract_title,
    flatten_block_results,
)
from notion_agent.vector_store import VectorStore, get_embedding_model

_MAX_TOKENS = 512
_OVERLAP = 64


class IngestionPipeline:
    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        self._settings = settings
        self._client = AsyncClient(auth=settings.notion_api_key)
        self._vector_store = VectorStore(persist_dir=settings.chroma_persist_dir)
        self._force_reindex = False

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return get_embedding_model().encode(texts, batch_size=32).tolist()

    async def _flatten_blocks(self, page_id: str) -> str:
        all_results: list[dict] = []
        cursor: str | None = None

        while True:
            kwargs: dict = {"block_id": page_id}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = await self._client.blocks.children.list(**kwargs)
            all_results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")

        return flatten_block_results(all_results)

    def _chunk_and_embed(self, page: NotionPage) -> list[ChunkedPage]:
        words = page.content.split()
        if not words:
            return []

        if len(words) <= _MAX_TOKENS:
            chunk_texts = [page.content]
        else:
            chunk_texts = []
            start = 0
            while start < len(words):
                end = min(start + _MAX_TOKENS, len(words))
                chunk_texts.append(" ".join(words[start:end]))
                if end == len(words):
                    break
                start = end - _OVERLAP

        embeddings = self._embed(chunk_texts)

        return [
            ChunkedPage(
                chunk_id=f"{page.id}_{i}",
                page_id=page.id,
                page_title=page.title,
                page_url=page.url,
                chunk_index=i,
                text=text,
                embedding=embeddings[i],
                metadata={
                    "last_edited_time": page.last_edited_time.isoformat(),
                    "created_by": page.created_by,
                    "last_edited_by": page.last_edited_by,
                    "is_database": page.is_database,
                },
            )
            for i, text in enumerate(chunk_texts)
        ]

    def _should_skip(self, page: NotionPage) -> bool:
        if getattr(self, "_force_reindex", False):
            return False
        last = self._vector_store.last_indexed_at(page.id)
        return last is not None and last >= page.last_edited_time

    def _parse_page(self, data: dict, content: str) -> NotionPage:
        props = data.get("properties", {})
        parent = data.get("parent", {})
        parent_id = parent.get("page_id") or parent.get("database_id")

        created_by_d = data.get("created_by", {})
        created_by = created_by_d.get("name") or created_by_d.get("id", "Unknown")
        edited_by_d = data.get("last_edited_by", {})
        last_edited_by = edited_by_d.get("name") or edited_by_d.get("id", "Unknown")

        return NotionPage(
            id=data["id"],
            title=extract_title(props),
            url=data.get("url", ""),
            parent_id=parent_id,
            last_edited_time=datetime.fromisoformat(data["last_edited_time"]),
            created_time=datetime.fromisoformat(data["created_time"]),
            created_by=created_by,
            last_edited_by=last_edited_by,
            content=content,
            properties=props,
            is_database=data.get("object") == "database",
        )

    async def fetch_page(self, page_id: str) -> NotionPage:
        data = await self._client.pages.retrieve(page_id=page_id)
        content = await self._flatten_blocks(page_id)
        return self._parse_page(data, content)

    async def _fetch_all_pages(self) -> tuple[list[NotionPage], int]:
        pages: list[NotionPage] = []
        skipped = 0
        cursor: str | None = None
        semaphore = asyncio.Semaphore(3)

        async def _sem(coro):
            async with semaphore:
                return await coro

        while True:
            kwargs: dict = {}
            if cursor:
                kwargs["start_cursor"] = cursor

            # Search is sequential (one call per loop iteration) — no semaphore needed.
            resp = await self._client.search(**kwargs)
            items = [r for r in resp.get("results", []) if r.get("object") in ("page", "database")]

            # Skip pages whose content hasn't changed since last index.
            to_fetch = []
            for item in items:
                if not self._force_reindex:
                    item_time = datetime.fromisoformat(item["last_edited_time"])
                    last = self._vector_store.last_indexed_at(item["id"])
                    if last is not None and last >= item_time:
                        skipped += 1
                        continue
                to_fetch.append(item)

            contents = await asyncio.gather(
                *[_sem(self._flatten_blocks(item["id"])) for item in to_fetch]
            )

            for item, content in zip(to_fetch, contents):
                pages.append(self._parse_page(item, content))

            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")

        return pages, skipped

    def run(self, force_reindex: bool = False) -> IngestionStats:
        self._force_reindex = force_reindex
        start = time.time()

        pages, pages_skipped = asyncio.run(self._fetch_all_pages())

        all_chunks: list[ChunkedPage] = []
        for page in pages:
            all_chunks.extend(self._chunk_and_embed(page))

        if all_chunks:
            self._vector_store.upsert(all_chunks)

        return IngestionStats(
            pages_fetched=len(pages) + pages_skipped,
            pages_skipped=pages_skipped,
            chunks_created=len(all_chunks),
            duration_seconds=time.time() - start,
        )
