"""FastAPI web UI for the Notion Intelligence Layer."""

from __future__ import annotations

import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from notion_agent.action_log import list_runs, rollback_run

app = FastAPI(title="Notion Intelligence")
_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_jobs: dict[str, dict] = {}


def _make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _run_agent(run_id: str, prompt: str, dry_run: bool) -> None:
    from notion_agent.agent import NotionAgent

    job = _jobs[run_id]
    q: queue.Queue = job["q"]

    def _emit(text: str) -> None:
        for line in text.splitlines():
            if line.strip():
                q.put(line)

    try:
        result = NotionAgent().run(
            prompt, verbose=True, dry_run=dry_run, output_callback=_emit
        )
        job["result"] = result
        job["status"] = "done"
    except Exception as exc:
        job["status"] = "error"
        q.put(f"ERROR: {exc}")
    finally:
        q.put(None)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    runs = list_runs(last_n=20)
    return _templates.TemplateResponse(
        request, "index.html", {"runs": list(reversed(runs))}
    )


@app.get("/runs/history", response_class=HTMLResponse)
async def history(request: Request) -> HTMLResponse:
    runs = list_runs(last_n=20)
    return _templates.TemplateResponse(
        request, "partials/history.html", {"runs": list(reversed(runs))}
    )


@app.post("/runs")
async def trigger_run(
    prompt: str = Form(...),
    dry_run: bool = Form(False),
) -> dict:
    run_id = _make_run_id()
    q: queue.Queue = queue.Queue()
    _jobs[run_id] = {"status": "running", "q": q, "result": None}
    threading.Thread(
        target=_run_agent, args=(run_id, prompt, dry_run), daemon=True
    ).start()
    return {"run_id": run_id}


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    if run_id not in _jobs:

        async def _not_found():
            yield "data: Run not found\n\nevent: done\ndata: \n\n"

        return StreamingResponse(_not_found(), media_type="text/event-stream")

    def _generate() -> Generator[str, None, None]:
        q = _jobs[run_id]["q"]
        while True:
            try:
                line = q.get(timeout=60)
                if line is None:
                    yield "event: done\ndata: \n\n"
                    break
                safe = line.replace("\n", " ").replace("\r", "")
                yield f"data: {safe}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


@app.post("/runs/{run_id}/rollback", response_class=HTMLResponse)
async def do_rollback(request: Request, run_id: str) -> HTMLResponse:
    try:
        archived = rollback_run(run_id)
        flash = f"Rolled back {len(archived)} page(s)."
    except ValueError as exc:
        flash = str(exc)
    runs = list_runs(last_n=20)
    return _templates.TemplateResponse(
        request, "index.html", {"runs": list(reversed(runs)), "flash": flash}
    )


def start(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port, log_level="warning")
