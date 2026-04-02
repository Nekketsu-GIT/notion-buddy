# Notion Intelligence Layer

A Python CLI that combines **RAG + MCP + Claude** to turn a Notion workspace into a queryable, agent-driven knowledge graph.

**Current status:** Proof of concept — all 4 phases complete and working.

Demo scenario: *"From the workspace pages, extract decisions, open questions, and next actions. Update the 'Décisions & questions ouvertes' page accordingly, with source citations."*

---

## How it works

```
CLI prompt
  └─► Agent (claude-sonnet-4-6, tool loop, max 10 iterations)
        ├─► RAG search  →  ChromaDB (local semantic index)
        └─► MCP tools   →  Notion REST API (read + write)
```

The key difference from Notion MCP or Claude chat: the workspace is **pre-indexed semantically**, so the agent can find relevant content across all pages without knowing their names in advance — then execute a full multi-step workflow autonomously from a single prompt.

---

## Quickstart

### 1. Prerequisites

- Python 3.11+
- A Notion workspace with an [integration key](https://www.notion.so/my-integrations)
- An Anthropic API key

### 2. Setup

```bash
git clone <repo>
cd notion-workflow-automation
make setup          # creates .venv + installs all deps
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # macOS/Linux
```

### 3. Configure

Copy `.env.example` to `.env` and fill in your keys:

```env
NOTION_API_KEY=secret_...
ANTHROPIC_API_KEY=sk-ant-...
NOTION_ROOT_PAGE_ID=        # optional: scope to a page subtree
CHROMA_PERSIST_DIR=./.chroma
LOG_LEVEL=INFO
```

> **Important:** add your Notion integration to every page you want indexed via the `...` → Connections menu in Notion.

### 4. Index your workspace

```bash
make ingest
# or: python -m notion_agent ingest
```

### 5. Run

```bash
# Semantic search (no writes)
make search Q="Q1 planning decisions"

# Full agent run with a custom prompt
make run P="Summarise all pages updated in the last 7 days"

# Pre-built demo scenario
make demo
```

---

## Docker

No external services needed — ChromaDB runs embedded. A named volume persists the index across runs.

```bash
make docker-build
make docker-ingest
make docker-search Q="your query"
make docker-run    P="your prompt"
make docker-demo
```

---

## Project structure

```
notion_agent/
├── config.py        — env vars + typed settings
├── models.py        — all dataclasses
├── ingestion.py     — fetch Notion pages → chunk → embed → ChromaDB
├── vector_store.py  — ChromaDB wrapper
├── mcp_server.py    — MCP stdio server (6 Notion tools)
├── agent.py         — Claude tool loop
└── __main__.py      — CLI entry points

tests/
├── test_ingestion.py
├── test_vector_store.py
└── test_mcp_tools.py
```

## Dependencies

| File | Install with | Purpose |
|---|---|---|
| `requirements.txt` | `make install` | Runtime (used in Docker) |
| `requirements-dev.txt` | `make setup` | Runtime + test tooling |

---

## Development

```bash
make check          # run full test suite (gate before any review or commit)
make test-cov       # tests + HTML coverage report
make test-fast      # stop on first failure
```

See `SPEC.md` for the full technical specification and `CLAUDE.md` for AI-navigation context, dev workflow, and the product vision.

---

## Implementation status

- [x] Phase 1 — Foundation (`config`, `models`, `ingestion`)
- [x] Phase 2 — RAG (`vector_store` + embeddings)
- [x] Phase 3 — MCP server (6 tools)
- [x] Phase 4 — Agent + demo

---

## Vision — what this needs to become a real product

The PoC proves the architecture works. The gap is not the AI logic — it's reliability, sync, trust, and UX.

| Layer | Today | Needed |
|---|---|---|
| Sync | Manual `make ingest` | Webhook / polling, < 5 min lag |
| Reliability | Best-effort | Retry, structured action log |
| Trust | Agent writes freely | Dry-run mode, rollback, scoped permissions |
| Scale | Embedded ChromaDB | Server-mode vector store, pagination |
| Interface | Terminal | Slack bot or minimal web UI |

**Next phases:**
- [ ] Phase 5 — Sync: incremental re-ingestion via webhook or polling
- [ ] Phase 6 — Trust: dry-run flag, action log, rollback, scoped write permissions
- [ ] Phase 7 — Scale: server-mode vector store, multi-workspace config
- [ ] Phase 8 — Interface: Slack bot or minimal web UI (run history, revert button)

Full roadmap in `SPEC.md`.
