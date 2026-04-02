# Notion Intelligence Layer

A Python CLI that combines **RAG + MCP + Claude** to turn a Notion workspace into a queryable, agent-driven knowledge graph.

Demo scenario: *"Find all Q1 planning pages, summarize key decisions, flag stale pages, and write an audit report back to Notion."*

---

## How it works

```
CLI prompt
  └─► Agent (claude-sonnet-4-6, tool loop)
        ├─► RAG search  →  ChromaDB (local embeddings)
        └─► MCP tools   →  Notion REST API
```

The agent reasons over semantic search results and Notion page content, then writes structured reports back to Notion — all from a single natural language prompt.

---

## Quickstart

### 1. Prerequisites

- Python 3.11+
- Docker (optional, for containerised runs)
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

> **Important:** add your Notion integration to every page/database you want indexed via the `...` → Connections menu in Notion.

### 4. Index your workspace

```bash
make ingest
# or: python -m notion_agent ingest
```

### 5. Run

```bash
# Semantic search (no writes)
make search Q="Q1 planning decisions"

# Full agent run
make run P="Summarise all pages updated in the last 7 days"

# Pre-built workspace audit demo
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
├── conftest.py          — shared fixtures + mock Notion client
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

See `SPEC.md` for the full technical specification and `CLAUDE.md` for AI-navigation context and dev workflow.

---

## Implementation status

- [ ] Phase 1 — Foundation (`config`, `models`, `ingestion`)
- [ ] Phase 2 — RAG (`vector_store` + embeddings)
- [ ] Phase 3 — MCP server (6 tools)
- [ ] Phase 4 — Agent + demo
