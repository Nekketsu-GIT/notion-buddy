# Notion Intelligence Layer — Technical Specification

## Overview

A Python-based AI system that treats a Notion workspace as a living knowledge graph.
It combines a semantic search layer (RAG) with an MCP-powered autonomous agent that
can read, reason over, and write back to Notion — all driven by a single natural
language prompt.

**Primary demo scenario:**
> "From the workspace pages, extract: (1) decisions, (2) open questions, (3) next actions.
> Update the 'Décisions & questions ouvertes' page accordingly, and cite the source page
> for each item."

---

## Goals

- Ingest and index an entire Notion workspace into a local vector store
- Expose semantic search over that index
- Build an MCP server that wraps Notion's API as agent-callable tools
- Wire a Claude agent that uses both RAG and MCP tools to execute multi-step workflows
- Produce a live, terminal-first demo runnable in under 5 minutes

## Non-Goals

- Web UI (CLI only)
- Real-time sync / webhooks (batch ingestion only)
- Multi-workspace support
- Production auth flows (single API key, single workspace)
- Confluence migration (separate project)

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                   CLI Entry Point                 │
│              python -m notion_agent run           │
└────────────────────┬─────────────────────────────┘
                     │  natural language prompt
                     ▼
          ┌──────────────────────┐
          │    Agent             │  claude-sonnet-4-6
          │    (tool loop)       │  max_iterations=10
          └───┬──────────────────┘
              │ uses
    ┌─────────┴──────────┐
    │                    │
    ▼                    ▼
┌────────────┐   ┌───────────────────┐
│ RAG Engine │   │ MCP Server        │
│ (search)   │   │ (Notion tools)    │
└─────┬──────┘   └────────┬──────────┘
      │                   │
      ▼                   ▼
┌────────────┐   ┌───────────────────┐
│ ChromaDB   │   │ Notion REST API   │
│ (local)    │   │ (notion-client)   │
└─────┬──────┘   └───────────────────┘
      │
      ▼
┌────────────┐
│ Ingestion  │
│ Pipeline   │
└────────────┘
```

---

## Tech Stack

| Layer | Library | Notes |
|---|---|---|
| LLM | `anthropic` — claude-sonnet-4-6 | Agent reasoning + tool calls |
| Embeddings | `sentence-transformers` — all-MiniLM-L6-v2 | Local, no extra API key |
| Vector store | `chromadb` — persistent local | Survives restarts |
| Notion client | `notion-client` | Official Python SDK |
| MCP server | `mcp` Python SDK | Stdio transport |
| CLI | `click` | Entry points |
| Config | `python-dotenv` | `.env` for secrets |

Python 3.11+. No web framework needed. ChromaDB runs **embedded** (local file, not a server), so no `docker-compose` is needed — a single container image suffices.

---

## Data Models

### `NotionPage`
```python
@dataclass
class NotionPage:
    id: str                    # Notion UUID
    title: str
    url: str
    parent_id: str | None      # None if top-level
    last_edited_time: datetime
    created_time: datetime
    created_by: str            # user display name
    last_edited_by: str        # user display name
    content: str               # flattened plain text from blocks
    properties: dict           # raw database properties if applicable
    is_database: bool
```

### `ChunkedPage`
```python
@dataclass
class ChunkedPage:
    chunk_id: str              # f"{page_id}_{chunk_index}"
    page_id: str
    page_title: str
    page_url: str
    chunk_index: int
    text: str                  # 512 token max per chunk
    embedding: list[float]     # 384-dim from all-MiniLM-L6-v2
    metadata: dict             # last_edited_time, created_by, etc.
```

### `SearchResult`
```python
@dataclass
class SearchResult:
    page_id: str
    page_title: str
    page_url: str
    chunk_text: str
    score: float               # cosine similarity 0–1
    last_edited_time: datetime
    last_edited_by: str
```

### `AuditEntry`
```python
@dataclass
class AuditEntry:
    page_id: str
    page_title: str
    page_url: str
    owner: str
    last_edited_time: datetime
    days_since_edit: int
    summary: str               # Claude-generated 2-3 sentence summary
    recommendation: str        # Claude-generated action
    status: Literal["stale", "active", "orphaned"]
```

---

## Component Specifications

### 1. Ingestion Pipeline (`notion_agent/ingestion.py`)

**Responsibility:** Fetch all pages from a Notion workspace, flatten block content
to plain text, persist to ChromaDB.

**Interface:**
```python
class IngestionPipeline:
    def run(self, force_reindex: bool = False) -> IngestionStats
    def fetch_page(self, page_id: str) -> NotionPage
    def _fetch_all_pages(self) -> list[NotionPage]
    def _flatten_blocks(self, page_id: str) -> str
    def _chunk_and_embed(self, page: NotionPage) -> list[ChunkedPage]
```

**Behavior:**
- Recursively fetches all pages via `search` endpoint + block children traversal
- Skips pages where `last_edited_time` is unchanged since last index (unless `force_reindex`)
- Rate limit: 3 requests/second (Notion's limit) — use `asyncio` + `asyncio.Semaphore(3)`
- Block types to flatten: `paragraph`, `heading_1/2/3`, `bulleted_list_item`,
  `numbered_list_item`, `to_do`, `toggle`, `quote`, `callout`, `code`
- Block types to skip: `image`, `video`, `file`, `pdf`, `embed`
- Chunk strategy: 512 tokens max, 64 token overlap, split on paragraph boundaries
- Embed with `sentence-transformers/all-MiniLM-L6-v2` (batch size 32)
- Store in ChromaDB collection `"notion_pages"` with full metadata

**IngestionStats:**
```python
@dataclass
class IngestionStats:
    pages_fetched: int
    pages_skipped: int         # unchanged since last run
    chunks_created: int
    duration_seconds: float
```

---

### 2. Vector Store (`notion_agent/vector_store.py`)

**Responsibility:** Wrap ChromaDB with a clean search interface.

**Interface:**
```python
class VectorStore:
    def search(self, query: str, top_k: int = 5) -> list[SearchResult]
    def upsert(self, chunks: list[ChunkedPage]) -> None
    def delete_page(self, page_id: str) -> None
    def count(self) -> int
    def last_indexed_at(self, page_id: str) -> datetime | None
```

**Behavior:**
- ChromaDB persistent client at `./.chroma`
- Collection name: `"notion_pages"`
- Query embeds the input string with the same model used at ingest
- Returns top_k results filtered by `score >= 0.3`
- Metadata filter support: `last_edited_by`, `is_database`, `days_since_edit`

---

### 3. MCP Server (`notion_agent/mcp_server.py`)

**Responsibility:** Expose Notion operations as MCP tools callable by the agent.

**Transport:** stdio (standard MCP pattern — agent spawns server as subprocess)

**Tools exposed:**

#### `search_workspace`
```
description: Semantic search over all indexed Notion pages.
input:
  query: str          — natural language search query
  top_k: int = 5      — number of results
  filter_stale: bool  — if true, only return pages not edited in 30+ days
output: list[SearchResult] as JSON
```

#### `get_page`
```
description: Fetch full content and metadata of a specific Notion page.
input:
  page_id: str
output: NotionPage as JSON
```

#### `list_database_entries`
```
description: List all entries in a Notion database with their properties.
input:
  database_id: str
  filter: dict | None  — Notion filter object (passed through)
output: list of page property dicts
```

#### `create_page`
```
description: Create a new Notion page (or database entry).
input:
  parent_id: str               — page or database ID
  parent_type: "page"|"database"
  title: str
  content: str                 — markdown-ish content, converted to blocks
  properties: dict | None      — database properties if parent is a database
output: { page_id: str, url: str }
```

#### `append_blocks`
```
description: Append content blocks to an existing Notion page.
input:
  page_id: str
  content: str                 — plain text / markdown, converted to blocks
output: { success: bool }
```

#### `update_page_property`
```
description: Update a single property on a Notion database entry.
input:
  page_id: str
  property_name: str
  value: str | number | bool
output: { success: bool }
```

**Content → Block conversion rules** (internal, used by `create_page` and `append_blocks`):
- `# text` → heading_1, `## text` → heading_2, `### text` → heading_3
- `- text` or `* text` → bulleted_list_item
- `1. text` → numbered_list_item
- `> text` → quote
- ` ```text``` ` → code block
- Everything else → paragraph

---

### 4. Agent (`notion_agent/agent.py`)

**Responsibility:** Orchestrate multi-step workflows using Claude + MCP tools.

**Interface:**
```python
class NotionAgent:
    def run(self, prompt: str, verbose: bool = True) -> AgentResult
```

**Behavior:**
- Model: `claude-sonnet-4-6`
- Tool loop: max 10 iterations, stop on `end_turn` or no tool calls
- MCP client connects to `mcp_server.py` via stdio subprocess
- System prompt defines the agent's persona and constraints (see below)
- Streams tool calls and responses to stdout when `verbose=True`
- Returns `AgentResult` with final answer + list of actions taken

**System prompt:**
```
You are a Notion workspace intelligence agent. You have access to tools that let
you search, read, and write to a Notion workspace.

When given a task:
1. Start by searching the workspace to understand what content exists
2. Fetch full details of the most relevant pages
3. Reason step-by-step before taking write actions
4. When creating audit reports or summaries, create them as Notion pages so the
   user has a persistent record
5. Always include page URLs in your final answer so the user can navigate directly

Be concise in your reasoning. Prefer action over explanation.
```

**AgentResult:**
```python
@dataclass
class AgentResult:
    final_answer: str
    actions_taken: list[str]   # human-readable log of each tool call
    pages_created: list[str]   # URLs of any pages created
    duration_seconds: float
    iterations: int
```

---

### 5. CLI (`notion_agent/__main__.py`)

**Commands:**

```
python -m notion_agent ingest [--force]
    Runs the ingestion pipeline. Prints IngestionStats on completion.

python -m notion_agent search <query> [--top-k 5]
    Runs a semantic search and prints results. No agent, no writes.
    Good for validating the RAG layer independently.

python -m notion_agent run <prompt>
    Runs the full agent with the given prompt.
    Streams tool calls to stdout in real time.

python -m notion_agent demo
    Runs the pre-built demo scenario end-to-end.
    Equivalent to: run "Find all pages related to Q1 planning..."
```

---

## Environment Configuration (`.env`)

```
NOTION_API_KEY=secret_...
NOTION_ROOT_PAGE_ID=           # optional: scope ingestion to a subtree
ANTHROPIC_API_KEY=sk-ant-...
CHROMA_PERSIST_DIR=./.chroma
LOG_LEVEL=INFO
```

---

## Demo Scenario (Workspace Audit)

**Setup:** A test Notion workspace with:
- 10–15 pages covering mixed topics (Q1 planning, team wiki, project pages)
- 3–4 pages last edited 30+ days ago
- Pages with and without clear ownership (assigned via a `Owner` property)

**Command:**
```bash
python -m notion_agent demo
```

**Expected agent behavior (step by step):**
1. `search_workspace("Q1 planning")` → finds relevant pages
2. `get_page(page_id)` × N → fetches full content of top results
3. `search_workspace("owner last updated stale", filter_stale=True)` → finds stale pages
4. Reasons over results, generates summaries and recommendations per page
5. `create_page(parent_id=ROOT, title="Workspace Audit — [date]", content=report)` → writes report

**Expected output page structure:**
```
# Workspace Audit — 2026-04-01

## Summary
- 12 pages scanned
- 4 pages stale (>30 days without edit)
- 2 pages with no assigned owner

## Stale Pages
| Page | Owner | Last Edited | Days | Recommendation |
|------|-------|-------------|------|----------------|
| Q1 Roadmap | Alice | 2026-02-15 | 45 | Needs Q2 update |
...

## Key Decisions Found (Q1 Planning)
- [summary of decisions extracted from pages]

## Action Items
- [ ] Alice: Update Q1 Roadmap
- [ ] Bob: Assign owner to "Team Norms" page
```

---

## File Structure

```
notion-workflow-automation/
├── SPEC.md                        ← this file
├── Makefile                       ← dev + docker targets
├── Dockerfile                     ← single-image CLI container
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt               ← runtime deps only (used in Docker)
├── requirements-dev.txt           ← -r requirements.txt + test tooling
├── notion_agent/
│   ├── __init__.py
│   ├── __main__.py                ← CLI entry points
│   ├── config.py                  ← loads .env, exposes settings
│   ├── models.py                  ← all dataclasses
│   ├── ingestion.py               ← IngestionPipeline
│   ├── vector_store.py            ← VectorStore (ChromaDB wrapper)
│   ├── mcp_server.py              ← MCP server (stdio)
│   └── agent.py                   ← NotionAgent (Claude + tool loop)
└── tests/
    ├── test_ingestion.py
    ├── test_vector_store.py
    └── test_mcp_tools.py
```

### Dependency files

| File | Who installs it | Purpose |
|---|---|---|
| `requirements.txt` | `make install`, Docker | Runtime-only — what the app needs to run |
| `requirements-dev.txt` | `make install-dev` / `make setup` | Adds pytest, mocks, coverage on top of runtime |

**When to update:**
- New runtime dep (notion-client, anthropic, etc.) → add to `requirements.txt` only
- New test/lint dep (pytest-*, respx, etc.) → add to `requirements-dev.txt` only
- Never pin exact versions in these files; pin ranges (`>=x.y`) and let `pip freeze` produce a lockfile if needed

---

## Implementation Phases

### Phase 1 — Foundation (2–3h)
- [ ] Repo setup: `requirements.txt`, `.env.example`, `.gitignore`
- [ ] `config.py` — load and validate env vars
- [ ] `models.py` — all dataclasses
- [ ] `ingestion.py` — Notion page fetch + block flattening
- [ ] Validate: `python -m notion_agent ingest` fetches real pages and prints stats

### Phase 2 — RAG Layer (2–3h)
- [ ] `vector_store.py` — ChromaDB wrapper
- [ ] Wire embeddings into ingestion pipeline
- [ ] `python -m notion_agent search "Q1 planning"` returns ranked results
- [ ] Validate: results are semantically relevant, not just keyword matches

### Phase 3 — MCP Server (2–3h)
- [ ] `mcp_server.py` — all 6 tools implemented
- [ ] Test each tool in isolation via MCP inspector or direct call
- [ ] Validate: `create_page` actually creates a page in Notion

### Phase 4 — Agent + Demo (2–3h)
- [ ] `agent.py` — Claude tool loop with MCP client
- [ ] `__main__.py` — all CLI commands
- [ ] Run full demo scenario end-to-end
- [ ] Polish: clean terminal output, timing stats, final page URL printed

---

## Success Criteria

| Criterion | Pass condition |
|---|---|
| Ingestion | Indexes 10+ pages in <60s |
| Semantic search | Top result is clearly relevant for 3 test queries |
| MCP write | `create_page` creates a real page in Notion with correct content |
| Agent | Completes demo scenario in <10 iterations without manual intervention |
| Demo | Runs end-to-end in <3 minutes with a fresh workspace |
| Code quality | Each component is independently testable |

---

## Current status

**Proof of concept — all 4 phases shipped and working.**

The demo runs end-to-end: one prompt → agent searches the workspace semantically, reads relevant
pages, reasons over content, and writes structured output (decisions, open questions, next actions
with source citations) back to Notion. Architecture is sound. The distance to a professional product
is not the AI logic — it's reliability, sync, trust, and UX.

---

## Vision — Road to a real product

### The honest gap

| Layer | PoC today | Product requirement |
|---|---|---|
| Sync | Manual `ingest` command | Continuous: webhook or polling, < 5 min lag |
| Reliability | Best-effort, silent failures possible | Retry, structured action log, no silent writes |
| Trust | Agent writes without confirmation | Dry-run mode, action log, rollback, scoped permissions |
| Scale | ChromaDB embedded, all pages in memory | Server-mode vector store, pagination, multi-workspace |
| Interface | Terminal only | Slack bot or minimal web UI with run history |

### What differentiates this from Notion MCP + Claude chat

**Notion MCP** gives Claude hands (tools to call the API).
**Claude chat** gives you a conversation.
**This project** adds the missing third piece: a pre-built semantic understanding of the whole
workspace so the agent can find relevant content and execute multi-step workflows autonomously —
without you driving each step or knowing in advance which pages matter.

Concrete difference: the demo ran one prompt → 5 agent iterations → structured content written to
the right Notion page with citations, touching 3 pages it was never told about.

### Realistic product paths

| Path | What you sell | First customer |
|---|---|---|
| **Vertical SaaS** | "Notion knowledge audit" — one polished workflow, $20–50/mo | Ops teams, chiefs of staff |
| **Agency / service** | Deliver audit reports and decision logs as a managed service | Companies with large Notion workspaces |
| **Internal tool** | Customized for one company's workspace | Setup + retainer, one paying client |

The agency path can start with this codebase. The SaaS path needs Phases 5–8 first.

### Next phases

- [ ] **Phase 5** — Sync: incremental re-ingestion via webhook or polling loop
- [ ] **Phase 6** — Trust: dry-run flag, structured action log, rollback, scoped write permissions
- [ ] **Phase 7** — Scale: server-mode vector store, ingestion pagination, multi-workspace config
- [ ] **Phase 8** — Interface: Slack bot or minimal web UI (run history, action log, revert button)
