# Notion Intelligence Layer — Claude Code Context

Full spec: `SPEC.md`. This file is the AI-navigation layer over it.

## What this project is

Python CLI that combines RAG + MCP + Claude agent over a Notion workspace.
Demo scenario: extract decisions, open questions, and next actions from workspace pages, then write structured output back to Notion with source citations.

**Current status:** Proof of concept / interview project. All 4 phases complete, demo runs end-to-end.
Full vision and roadmap to a real product: see `## Vision` at the bottom of this file.

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

## Non-goals (do not implement — PoC scope)

- Web UI — CLI only
- Real-time sync / webhooks — batch ingestion only
- Multi-workspace support
- Confluence migration

## Implementation phases

- [x] **Phase 1** — Foundation: `config.py`, `models.py`, `ingestion.py` (fetch + flatten)
  - Gate: `python -m notion_agent ingest` fetches real pages and prints stats
- [x] **Phase 2** — RAG: `vector_store.py` + wire embeddings into ingestion
  - Gate: `python -m notion_agent search "Q1 planning"` returns relevant results
- [x] **Phase 3** — MCP: `mcp_server.py` — all 6 tools
  - Gate: `create_page` creates a real page in Notion
- [x] **Phase 4** — Agent + Demo: `agent.py`, `__main__.py`, end-to-end demo
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

## Vision

### Where this stands vs. a real product

This PoC proves the architecture works. The gap to a professional tool is not the AI logic — it's
reliability, sync, trust, and UX. None are unsolvable, all are significant work.

### What needs to be true before this is sellable

**1. Continuous sync (highest leverage)**
- Replace `make ingest` with a webhook listener or a background polling loop
- Notion sends page-update events → re-embed only changed pages
- Without this, the vector index is stale minutes after any edit
- Target: index lag < 5 minutes

**2. Agent reliability**
- Add retry + exponential backoff on Notion API and Anthropic API calls
- Add a dry-run mode: agent describes what it would write before writing
- Add a structured action log (what was written, when, by which run)
- Non-determinism is acceptable; silent failure is not

**3. Trust layer (required before any real user touches this)**
- Dry-run flag: `make run P="..." --dry-run` prints the diff, writes nothing
- Confirmation prompt before any write action (optional, off by default)
- Rollback: keep a snapshot of pages before agent modifies them
- Scoped permissions: agent should only have write access to pages you explicitly allow

**4. Scale**
- ChromaDB embedded works to ~5 000 pages; above that, move to a server-mode or Qdrant
- Add pagination to ingestion (currently loads all pages into memory)
- Multi-workspace: one config file per workspace, shared vector store infra

**5. UX (required to sell to non-technical users)**
- The people who would pay for this do not use a terminal
- Minimum viable interface: a Slack bot or a Notion button that triggers a run
- Ideal: a small web UI with run history, action log, and a "revert last run" button

### Realistic product paths

| Path | What you sell | Who buys |
|---|---|---|
| **Vertical SaaS** | "Notion knowledge audit" as a polished one-workflow tool | Ops teams, chiefs of staff, $20–50/mo |
| **Agency / service** | Deliver the output (audit reports, decision logs) as a managed service | Companies with large Notion workspaces, project-based pricing |
| **Internal tool** | Build a customized version for one company's workspace | One paying client, setup + retainer |

The vertical SaaS path requires the full trust layer + a web UI before the first paying user.
The agency path can start tomorrow with the current codebase.

### Next phases (when you come back to this)

- [ ] **Phase 5** — Sync: webhook or polling-based incremental re-ingestion
- [ ] **Phase 6** — Trust: dry-run mode, action log, rollback, scoped write permissions
- [ ] **Phase 7** — Scale: server-mode vector store, pagination, multi-workspace config
- [ ] **Phase 8** — Interface: Slack bot or minimal web UI (run history + revert)
