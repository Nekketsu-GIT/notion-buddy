# Phases — Notion Intelligence Layer

Tracks implementation progress across all phases. Update status and test counts after each session.

---

## Phase 1 — Foundation

**Status:** complete

**Description:** Core data models and ingestion pipeline. Fetch Notion pages, flatten blocks into plain text, chunk content, and persist to ChromaDB. Includes `config.py`, `models.py`, `ingestion.py`.

**Gate:** `python -m notion_agent ingest` fetches real pages and prints stats.

**Test file:** `tests/test_ingestion.py`
**Tests passing:** 11 / 11

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phase 1 is complete (11/11 tests passing).
Start Phase 2: implement vector_store.py (ChromaDB wrapper with .search(), .upsert(), .delete_page())
and wire embeddings into ingestion.py. Use sentence-transformers/all-MiniLM-L6-v2, batch size 32.
Run `make test` after each change. Gate: `python -m notion_agent search "Q1 planning"` returns relevant results.
```

---

## Phase 2 — RAG

**Status:** complete

**Description:** Semantic search layer. `vector_store.py` wraps ChromaDB with `.search()`, `.upsert()`, `.delete_page()`. Embeddings wired into ingestion pipeline using `sentence-transformers/all-MiniLM-L6-v2`.

**Gate:** `python -m notion_agent search "Q1 planning"` returns relevant results.

**Test file:** `tests/test_vector_store.py`
**Tests passing:** 8 / 8

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phases 1–2 are complete (19/19 tests passing).
Start Phase 3: implement mcp_server.py exposing 6 Notion tools via MCP stdio transport:
search_workspace, get_page, list_database_entries, create_page, append_blocks, update_page_property.
Run `make test` after each change. Gate: `create_page` creates a real page in Notion.
```

---

## Phase 3 — MCP Server

**Status:** complete

**Description:** MCP stdio server exposing 6 Notion tools to the agent. Tools: `search_workspace`, `get_page`, `list_database_entries`, `create_page`, `append_blocks`, `update_page_property`.

**Gate:** `create_page` creates a real page in Notion.

**Test file:** `tests/test_mcp_tools.py`
**Tests passing:** 23 / 23

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phases 1–3 are complete (42/42 tests passing).
Start Phase 4: implement agent.py (NotionAgent: Claude claude-sonnet-4-6 + MCP tool loop, max 10 iterations)
and __main__.py (CLI: ingest | search | run | demo). The demo should extract decisions, open questions,
and next actions from workspace pages and write structured output back to Notion with source citations.
Run `make test` after each change. Gate: demo completes in <10 iterations, <3 minutes.
```

---

## Phase 4 — Agent + Demo

**Status:** complete

**Description:** `agent.py` implements the Claude claude-sonnet-4-6 + MCP tool loop (max 10 iterations). `__main__.py` wires the CLI: `ingest | search | run | demo`. Demo extracts decisions, open questions, and next actions from workspace pages and writes structured output back to Notion with source citations.

**Gate:** Demo completes in <10 iterations, <3 minutes.

**Test file:** *(no automated tests — gate is a manual end-to-end demo run)*
**Tests passing:** N/A

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phases 1–4 are complete (42/42 tests passing, demo runs end-to-end).
Start Phase 5: implement continuous sync. Replace `make ingest` with a webhook listener or background
polling loop. Notion page-update events should trigger re-embedding of only changed pages.
Target: index lag < 5 minutes. See the Vision section in CLAUDE.md for full requirements.
```

---

## Phase 5 — Sync

**Status:** not started

**Description:** Continuous sync via webhook listener or background polling loop. Only re-embed changed pages. Target index lag < 5 minutes.

**Test file:** `tests/test_sync.py` *(not yet written)*
**Tests passing:** 0 / 0

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phase 5 is not started.
Implement continuous sync: a webhook listener or polling loop that detects Notion page changes
and re-embeds only the changed pages using the existing ingestion pipeline.
Write tests in tests/test_sync.py first, then implement. Target index lag < 5 minutes.
Run `make test` after each change.
```

---

## Phase 6 — Trust Layer

**Status:** not started

**Description:** Dry-run mode, action log, rollback, and scoped write permissions. Agent describes what it would write before writing. Snapshot pages before modification. Only write to explicitly allowed pages.

**Test file:** `tests/test_trust.py` *(not yet written)*
**Tests passing:** 0 / 0

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phase 6 is not started.
Implement the trust layer:
1. --dry-run flag: agent prints the diff, writes nothing
2. Action log: structured record of what was written, when, by which run
3. Rollback: snapshot pages before agent modifies them
4. Scoped permissions: agent only writes to explicitly allowed pages
Write tests in tests/test_trust.py first, then implement. Run `make test` after each change.
```

---

## Phase 7 — Scale

**Status:** not started

**Description:** Server-mode vector store (Qdrant or ChromaDB server), pagination in ingestion (no more loading all pages into memory), multi-workspace config.

**Test file:** `tests/test_scale.py` *(not yet written)*
**Tests passing:** 0 / 0

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phase 7 is not started.
Implement scale improvements:
1. Migrate vector store from embedded ChromaDB to server-mode (Qdrant or ChromaDB server)
2. Add pagination to ingestion — no loading all pages into memory
3. Add multi-workspace support: one config per workspace, shared vector store infra
Write tests in tests/test_scale.py first, then implement. Run `make test` after each change.
```

---

## Phase 8 — Interface

**Status:** not started

**Description:** Slack bot or minimal web UI with run history, action log, and "revert last run" button. Target: non-technical users can trigger runs without a terminal.

**Test file:** `tests/test_interface.py` *(not yet written)*
**Tests passing:** 0 / 0

**Next session prompt:**
```
Read CLAUDE.md and PHASES.md to orient yourself. Phase 8 is not started.
Implement a minimal interface for non-technical users. Options in priority order:
1. Slack bot: slash command triggers a run, posts results in thread
2. Web UI: run history, action log, "revert last run" button
Choose the simpler option first. Write tests where possible. Gate: a non-technical user
can trigger a demo run and see results without touching the terminal.
```
