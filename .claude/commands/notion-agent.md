---
description: Run or develop the Notion Intelligence Layer agent (ingest / search / run / demo / test)
---

You are working inside the **Notion Intelligence Layer** project — a Python CLI that combines RAG + MCP + Claude agent over a Notion workspace.

## Project layout (quick reference)
```
notion_agent/
  config.py       — env settings
  models.py       — all dataclasses
  ingestion.py    — IngestionPipeline (fetch → chunk → embed → ChromaDB)
  vector_store.py — VectorStore (ChromaDB wrapper)
  mcp_server.py   — MCP stdio server (6 tools)
  agent.py        — NotionAgent (Claude claude-sonnet-4-6 + tool loop)
  __main__.py     — CLI entry point
tests/
  conftest.py     — shared fixtures (mock Notion client, mock VectorStore, sample models)
  test_ingestion.py
  test_vector_store.py
  test_mcp_tools.py
```

## Commands you can run (inside .venv)

| Goal | Command |
|---|---|
| Full first-time setup | `make setup` |
| Run tests | `make test` |
| Tests with coverage | `make test-cov` |
| Index workspace | `make ingest` |
| Force re-index | `make ingest-force` |
| Semantic search | `make search Q="<query>"` |
| Run agent | `make run P="<prompt>"` |
| Run demo | `make demo` |
| Clean artefacts | `make clean` |

## What the user is asking you to do

$ARGUMENTS

## Guidelines
- If the user asked for a **command** (e.g. "run the demo", "search for Q1 planning"), translate it into the correct `make` or `python -m notion_agent` invocation and explain what it does.
- If the user asked about **implementation** (e.g. "how does chunking work?"), point to the relevant module and method from the layout above.
- If the user asked to **write or fix code**, follow the conventions in CLAUDE.md exactly:
  - All dataclasses go in `models.py`
  - Notion rate limit: `asyncio.Semaphore(3)`
  - Chunk size 512 tokens, 64 overlap
  - Search score threshold `>= 0.3`
  - Model: `claude-sonnet-4-6`
- Check the Implementation Phases in CLAUDE.md to know which gate has to pass before moving on.
