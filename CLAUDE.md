# Notion Intelligence Layer — Claude Code Context

Full spec: `SPEC.md`. This file is the AI-navigation layer over it.

## What this project is

Python CLI that combines RAG + MCP + Claude agent over a Notion workspace.
Demo scenario: "Find all Q1 planning pages, summarize decisions, flag stale pages, write audit report to Notion."

## Architecture (one line per module)

```
notion_agent/
├── config.py        — load/validate .env, expose typed settings
├── models.py        — all dataclasses (NotionPage, ChunkedPage, SearchResult, AuditEntry, AgentResult)
├── ingestion.py     — IngestionPipeline: fetch Notion pages → flatten blocks → chunk → embed → ChromaDB
├── vector_store.py  — VectorStore: ChromaDB wrapper with .search(), .upsert(), .delete_page()
├── mcp_server.py    — MCP stdio server exposing 6 Notion tools to the agent
├── agent.py         — NotionAgent: Claude claude-sonnet-4-6 + MCP tool loop (max 10 iterations)
└── __main__.py      — CLI: ingest | search | run | demo
```

## Key commands

```bash
python -m notion_agent ingest [--force]      # index workspace into ChromaDB
python -m notion_agent search "<query>"      # semantic search only, no writes
python -m notion_agent run "<prompt>"        # full agent run
python -m notion_agent demo                  # pre-built audit scenario
```

## MCP tools (mcp_server.py)

| Tool | Purpose |
|---|---|
| `search_workspace` | Semantic search over ChromaDB index |
| `get_page` | Fetch full content + metadata of a page |
| `list_database_entries` | List Notion database rows |
| `create_page` | Create page or database entry |
| `append_blocks` | Append content to existing page |
| `update_page_property` | Update a single database property |

## Conventions

- All dataclasses live in `models.py` — never define them inline elsewhere
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`, batch size 32, 384-dim
- ChromaDB collection name: `"notion_pages"`, persist dir: `./.chroma`
- Notion rate limit: 3 req/s — use `asyncio.Semaphore(3)` in ingestion
- Chunk size: 512 tokens max, 64 token overlap, split on paragraph boundaries
- Search score threshold: `>= 0.3` (filter out low-confidence results)
- MCP transport: stdio (agent spawns server as subprocess)
- Content → Notion blocks: `#` → heading_1, `-`/`*` → bulleted_list, `>` → quote, ` ``` ` → code

## Non-goals (do not implement)

- Web UI — CLI only
- Real-time sync / webhooks — batch ingestion only
- Multi-workspace support
- Confluence migration

## Implementation phases

- [ ] **Phase 1** — Foundation: `config.py`, `models.py`, `ingestion.py` (fetch + flatten)
  - Gate: `python -m notion_agent ingest` fetches real pages and prints stats
- [ ] **Phase 2** — RAG: `vector_store.py` + wire embeddings into ingestion
  - Gate: `python -m notion_agent search "Q1 planning"` returns relevant results
- [ ] **Phase 3** — MCP: `mcp_server.py` — all 6 tools
  - Gate: `create_page` creates a real page in Notion
- [ ] **Phase 4** — Agent + Demo: `agent.py`, `__main__.py`, end-to-end demo
  - Gate: demo completes in <10 iterations, <3 minutes

## Dev workflow (per phase)

Follow this cycle for each phase:

```
1. Implement the module(s) for the phase
2. make check          ← tests must be green before moving on
3. /simplify           ← code review: quality, reuse, dead weight
4. Fix review findings, re-run make check
5. Hit the phase gate (manual CLI smoke test)
6. Update the checkbox above, move to next phase
```

**Rules:**
- Never skip the gate test — each phase gate validates real Notion API connectivity
- Tests are written ahead of implementation (they're already in `tests/`) — make them pass, don't rewrite them to fit bad implementations
- `/simplify` reviews **staged files only** — stage the files you want reviewed with `git add` before running it, so the review is scoped and fast
- `make check` = `make test` — all tests must pass before a review or gate

## Environment variables

```
NOTION_API_KEY=secret_...
NOTION_ROOT_PAGE_ID=        # optional: scope ingestion to a subtree
ANTHROPIC_API_KEY=sk-ant-...
CHROMA_PERSIST_DIR=./.chroma
LOG_LEVEL=INFO
```
