"""Command line entry point for querying content_info."""
import json
from pathlib import Path
from typing import Optional

import click
import structlog

from analysis import PosterAnalysisPipeline, SafeZoneAnalyzer, SAFE_ZONE_PROMPT
from config import get_config
from exceptions import ContentNotFoundError, DatabricksError
from service import ContentService

logger = structlog.get_logger(__name__)


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    )


@click.group()
def cli():
    """Utilities for querying Databricks content_info."""
    configure_logging()


@cli.command()
@click.argument("content_id")
def get(content_id: str):
    """Retrieve all rows for CONTENT_ID."""
    service = ContentService()
    try:
        records = service.get_content(content_id)
        click.echo(json.dumps([record.__dict__ for record in records], default=str, indent=2))
    except ContentNotFoundError:
        click.echo(f"No records for content_id={content_id}")
    except DatabricksError as exc:
        logger.error("command_failed", error=str(exc))
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.argument("keyword")
@click.option("--limit", default=10, show_default=True)
def search(keyword: str, limit: int):
    """Search content by keyword."""
    service = ContentService()
    try:
        records = service.search(keyword, limit=limit)
        click.echo(json.dumps([record.__dict__ for record in records], default=str, indent=2))
    except DatabricksError as exc:
        logger.error("command_failed", error=str(exc))
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.argument("content_ids", nargs=-1)
def bulk(content_ids):
    """Fetch many content ids at once."""
    service = ContentService()
    try:
        results = service.get_bulk_content(list(content_ids))
        serializable = {
            cid: [record.__dict__ for record in records] for cid, records in results.items()
        }
        click.echo(json.dumps(serializable, default=str, indent=2))
    except DatabricksError as exc:
        logger.error("command_failed", error=str(exc))
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.option("--batch-size", default=1000, show_default=True)
@click.option("--include-inactive", is_flag=True, help="Include inactive content")
@click.option("--allow-null", is_flag=True, help="Allow rows with missing URLs")
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Stop after emitting this many rows (default: stream all)",
)
def posters(batch_size: int, include_inactive: bool, allow_null: bool, limit: Optional[int]):
    """Stream poster image URLs for downstream processing."""
    service = ContentService()
    try:
        iterator = service.iter_poster_images(
            batch_size=batch_size,
            only_active=not include_inactive,
            require_url=not allow_null,
            max_items=limit,
        )
        for poster in iterator:
            click.echo(json.dumps(poster.__dict__, default=str))
    except DatabricksError as exc:
        logger.error("command_failed", error=str(exc))
        raise click.ClickException(str(exc)) from exc


@cli.command("analyze-posters")
@click.option("--limit", default=5, show_default=True, help="Number of posters to analyze")
@click.option("--batch-size", default=50, show_default=True)
@click.option("--include-inactive", is_flag=True, help="Include inactive content rows")
@click.option("--allow-null", is_flag=True, help="Allow rows missing URLs")
@click.option(
    "--provider",
    type=click.Choice(["openai"]),
    default="openai",
    show_default=True,
)
@click.option(
    "--prompt-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to custom prompt text file (defaults to built-in safe-zone prompt).",
)
@click.option(
    "--json-array",
    is_flag=True,
    help="Emit a single JSON array instead of NDJSON.",
)
def analyze_posters(
    limit: int,
    batch_size: int,
    include_inactive: bool,
    allow_null: bool,
    provider: str,
    prompt_file: Optional[Path],
    json_array: bool,
):
    """Run safe-zone analysis via the configured vision provider."""
    config = get_config()
    prompt_text = SAFE_ZONE_PROMPT if not prompt_file else prompt_file.read_text(encoding="utf-8")

    analyzer = SafeZoneAnalyzer(
        provider=provider,
        model=config.openai_model,
        prompt=prompt_text,
        api_key=config.openai_api_key,
    )
    pipeline = PosterAnalysisPipeline(ContentService(), analyzer, config=config)

    results = pipeline.run(
        limit=limit,
        batch_size=batch_size,
        include_inactive=include_inactive,
        allow_null_urls=allow_null,
    )

    serializable = [result.to_dict() for result in results]

    if json_array:
        click.echo(json.dumps(serializable, indent=2))
    else:
        for row in serializable:
            click.echo(json.dumps(row))


@cli.command()
def health():
    """Run a lightweight health check."""
    from connection import get_connection_provider

    try:
        provider = get_connection_provider()
        with provider.cursor() as cursor:
            cursor.execute("SELECT current_timestamp()")
            cursor.fetchone()
        click.echo("OK")
    except DatabricksError as exc:
        logger.error("health_check_failed", error=str(exc))
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":
    cli()

