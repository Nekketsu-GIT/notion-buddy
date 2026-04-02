"""Action logger: records every agent run and supports rollback of created pages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(".agent_log")
LOG_FILE = LOG_DIR / "runs.jsonl"


def log_run(
    run_id: str,
    prompt: str,
    dry_run: bool,
    result: object,  # AgentResult
    pages_created_ids: list[str],
) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    entry = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "dry_run": dry_run,
        "iterations": result.iterations,          # type: ignore[attr-defined]
        "duration_seconds": round(result.duration_seconds, 2),  # type: ignore[attr-defined]
        "actions_taken": result.actions_taken,    # type: ignore[attr-defined]
        "pages_created": result.pages_created,    # type: ignore[attr-defined]
        "pages_created_ids": pages_created_ids,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_runs(last_n: int = 10) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-last_n:]


def rollback_run(run_id: str) -> list[str]:
    """Archive all Notion pages created during run_id. Returns list of archived page IDs."""
    all_runs = {r["run_id"]: r for r in list_runs(last_n=1000)}
    if run_id not in all_runs:
        raise ValueError(f"Run {run_id!r} not found in log.")

    run = all_runs[run_id]
    if run["dry_run"]:
        raise ValueError(f"Run {run_id!r} was a dry run — nothing to roll back.")

    page_ids = run.get("pages_created_ids", [])
    if not page_ids:
        return []

    from notion_agent.config import get_settings
    from notion_client import Client

    notion = Client(auth=get_settings().notion_api_key)
    archived: list[str] = []
    for page_id in page_ids:
        try:
            notion.pages.update(page_id=page_id, archived=True)
            archived.append(page_id)
        except Exception as exc:
            print(f"Warning: could not archive {page_id}: {exc}")
    return archived
