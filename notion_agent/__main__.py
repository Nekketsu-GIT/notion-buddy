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
def run(prompt: str) -> None:
    """Run the full agent with a natural language prompt."""
    from notion_agent.agent import NotionAgent
    agent = NotionAgent()
    result = agent.run(prompt)
    click.echo(result.final_answer)


@cli.command()
def serve() -> None:
    """Start the MCP stdio server (used internally by the agent)."""
    from notion_agent.mcp_server import run_server
    run_server()


@cli.command()
def demo() -> None:
    """Run the pre-built workspace audit demo."""
    from notion_agent.agent import NotionAgent
    prompt = (
        "From the workspace pages, extract: (1) decisions, (2) open questions, "
        "(3) next actions. Update the 'Décisions & questions ouvertes' page "
        "accordingly, and cite the source page for each item."
    )
    agent = NotionAgent()
    result = agent.run(prompt)
    click.echo(result.final_answer)
    if result.pages_created:
        click.echo("\nPages created:")
        for url in result.pages_created:
            click.echo(f"  {url}")


if __name__ == "__main__":
    cli()
