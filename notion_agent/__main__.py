"""CLI entry points for the Notion Intelligence Layer."""

from __future__ import annotations

import sys

import click

# Ensure stdout/stderr can handle Unicode (e.g. emojis in Claude responses) on Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from notion_agent.ingestion import IngestionPipeline
from notion_agent.vector_store import VectorStore


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Force re-index of all pages.")
def ingest(force: bool) -> None:
    """Index the Notion workspace into ChromaDB."""
    pipeline = IngestionPipeline()
    stats = pipeline.run(force_reindex=force)
    click.echo(f"Pages fetched:  {stats.pages_fetched}")
    click.echo(f"Pages skipped:  {stats.pages_skipped}")
    click.echo(f"Chunks created: {stats.chunks_created}")
    click.echo(f"Duration:       {stats.duration_seconds:.1f}s")


@cli.command()
@click.argument("query")
@click.option("--top-k", default=5, show_default=True)
def search(query: str, top_k: int) -> None:
    """Semantic search over the indexed workspace."""
    from notion_agent.config import get_settings

    settings = get_settings()
    store = VectorStore(persist_dir=settings.chroma_persist_dir)
    results = store.search(query, top_k=top_k)
    if not results:
        click.echo("No results found.")
        return
    for r in results:
        click.echo(f"[{r.score:.2f}] {r.page_title}")
        click.echo(f"       {r.page_url}")
        click.echo(f"       {r.chunk_text[:120]}")
        click.echo()


@cli.command()
@click.argument("prompt")
@click.option("--dry-run", is_flag=True, help="Describe writes without executing them.")
def run(prompt: str, dry_run: bool) -> None:
    """Run the full agent with a natural language prompt."""
    from notion_agent.agent import NotionAgent

    result = NotionAgent().run(prompt, dry_run=dry_run)
    click.echo(result.final_answer)
    click.echo(
        f"\nRun ID: {result.run_id}  ({result.iterations} iterations, {result.duration_seconds:.1f}s)"
    )


@cli.command()
def serve() -> None:
    """Start the MCP stdio server (used internally by the agent)."""
    from notion_agent.mcp_server import run_server

    run_server()


@cli.command()
@click.option("--dry-run", is_flag=True, help="Describe writes without executing them.")
def demo(dry_run: bool) -> None:
    """Run the pre-built workspace audit demo."""
    from notion_agent.agent import NotionAgent

    prompt = (
        "From the workspace pages, extract: (1) decisions, (2) open questions, "
        "(3) next actions. Update the 'Décisions & questions ouvertes' page "
        "accordingly, and cite the source page for each item."
    )
    result = NotionAgent().run(prompt, dry_run=dry_run)
    click.echo(result.final_answer)
    if result.pages_created:
        click.echo("\nPages created:")
        for url in result.pages_created:
            click.echo(f"  {url}")
    click.echo(
        f"\nRun ID: {result.run_id}  ({result.iterations} iterations, {result.duration_seconds:.1f}s)"
    )


@cli.command("log")
@click.option("--last", default=10, show_default=True, help="Number of runs to show.")
def show_log(last: int) -> None:
    """Show recent agent runs."""
    from notion_agent.action_log import list_runs

    runs = list_runs(last_n=last)
    if not runs:
        click.echo("No runs logged yet.")
        return
    for r in runs:
        flag = "  [DRY RUN]" if r["dry_run"] else ""
        pages = (
            f"  → {len(r['pages_created'])} page(s) created"
            if r["pages_created"]
            else ""
        )
        click.echo(
            f"{r['run_id']}{flag}  {r['timestamp'][:19]}  {r['iterations']} iter  {r['duration_seconds']}s{pages}"
        )
        click.echo(f"  {r['prompt'][:100]}")
        click.echo()


@cli.command()
@click.argument("run_id")
def rollback(run_id: str) -> None:
    """Archive all Notion pages created by a run. Use 'log' to find run IDs."""
    from notion_agent.action_log import rollback_run

    try:
        archived = rollback_run(run_id)
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        raise SystemExit(1)
    if archived:
        click.echo(f"Archived {len(archived)} page(s):")
        for pid in archived:
            click.echo(f"  {pid}")
    else:
        click.echo("No pages to roll back (run created no pages).")


if __name__ == "__main__":
    cli()
