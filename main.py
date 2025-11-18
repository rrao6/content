"""Command line entry point for querying content_info."""
import json
import json as json_lib  # Add alias for consistency
from pathlib import Path
from typing import Optional

import click
import structlog

from analysis import PosterAnalysisPipeline, SafeZoneAnalyzer, SAFE_ZONE_PROMPT
from config import get_config
from exceptions import ContentNotFoundError, DatabricksError
from service import ContentService, EligibleTitlesService
from sot_pipeline import SOTAnalysisPipeline

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
@click.option(
    "--no-download",
    is_flag=True,
    help="Skip image download and use URLs directly (not recommended for HTTP URLs).",
)
@click.option(
    "--download-timeout",
    default=20,
    help="Timeout in seconds for image downloads.",
)
@click.option(
    "--save-composite-images",
    is_flag=True,
    help="Save composite images with red zone overlay for debugging/verification.",
)
@click.option(
    "--composite-image-dir",
    default="./debug_composite_images",
    help="Directory to save composite images (default: ./debug_composite_images).",
)
def analyze_posters(
    limit: int,
    batch_size: int,
    include_inactive: bool,
    allow_null: bool,
    provider: str,
    prompt_file: Optional[Path],
    json_array: bool,
    no_download: bool,
    download_timeout: int,
    save_composite_images: bool,
    composite_image_dir: str,
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
        download_images=not no_download,
        download_timeout=download_timeout,
        save_composite_images=save_composite_images,
        composite_image_dir=composite_image_dir,
    )

    serializable = [result.to_dict() for result in results]

    if json_array:
        click.echo(json.dumps(serializable, indent=2))
    else:
        for row in serializable:
            click.echo(json.dumps(row))


@cli.command()
def metrics():
    """Display current metrics and monitoring status."""
    from monitoring import get_analysis_monitor
    import json as json_lib
    
    monitor = get_analysis_monitor()
    stats = monitor.get_health_status()
    
    # Pretty print the metrics
    click.echo(json_lib.dumps(stats, indent=2))
    
    # Highlight any alerts
    if stats['alerts']:
        click.echo("\n⚠️  ACTIVE ALERTS:")
        for alert in stats['alerts']:
            click.echo(f"  - {alert}")
    else:
        click.echo("\n✅ No active alerts")


@cli.command()
@click.option(
    "--days-back", 
    default=7, 
    type=int, 
    help="Number of days to look back (default: 7)"
)
@click.option(
    "--sot-type", 
    multiple=True, 
    help="Filter by SOT type (can specify multiple)"
)
@click.option(
    "--export",
    type=click.Path(),
    help="Export results to JSON file"
)
def eligible_titles(days_back: int, sot_type: tuple, export: Optional[str]):
    """List eligible titles from Sources of Truth."""
    service = EligibleTitlesService()
    
    try:
        # Get counts by SOT type
        counts = service.count_eligible_titles(days_back=days_back)
        
        # Filter SOT types if specified
        sot_types = list(sot_type) if sot_type else None
        
        click.echo(f"\nEligible Titles Summary (last {days_back} days):")
        click.echo("-" * 50)
        
        total = 0
        for sot_name, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            if not sot_types or sot_name in sot_types:
                click.echo(f"{sot_name:15} {count:6,} titles")
                total += count
        
        click.echo("-" * 50)
        click.echo(f"{'TOTAL':15} {total:6,} titles")
        
        # Export if requested
        if export:
            click.echo(f"\nExporting eligible titles to {export}...")
            
            titles = service.get_eligible_poster_images(
                days_back=days_back,
                sot_types=sot_types
            )
            
            export_data = []
            for title in titles:
                export_data.append({
                    "program_id": title.program_id,
                    "content_id": title.content_id,
                    "sot_name": title.sot_name,
                    "content_name": title.content_name,
                    "content_type": title.content_type,
                    "poster_img_url": title.poster_img_url,
                })
            
            with open(export, "w") as f:
                json_lib.dump(export_data, f, indent=2)
            
            click.echo(f"Exported {len(export_data)} titles with poster URLs")
            
    except DatabricksError as exc:
        logger.error("eligible_titles_failed", error=str(exc))
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.option(
    "--days-back",
    default=7,
    type=int,
    help="Number of days to look back (default: 7)"
)
@click.option(
    "--sot-type",
    multiple=True,
    help="Filter by SOT type (can specify multiple)"
)
@click.option(
    "--batch-size",
    default=100,
    type=int,
    help="Number of posters to fetch per batch"
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of posters to analyze"
)
@click.option(
    "--json-array",
    is_flag=True,
    help="Output as single JSON array instead of NDJSON"
)
@click.option(
    "--output",
    type=click.Path(),
    help="Write results to file"
)
@click.option(
    "--no-download",
    is_flag=True,
    help="Skip image download (use direct URLs)"
)
@click.option(
    "--download-timeout",
    default=20,
    type=int,
    help="Timeout for image downloads in seconds"
)
def analyze_eligible(
    days_back: int,
    sot_type: tuple,
    batch_size: int,
    limit: Optional[int],
    json_array: bool,
    output: Optional[str],
    no_download: bool,
    download_timeout: int,
):
    """Analyze posters for eligible titles from Sources of Truth."""
    config = get_config()
    
    if not config.openai_api_key:
        raise click.ClickException(
            "OpenAI API key required. Set OPENAI_API_KEY in .env file."
        )
    
    # Initialize services
    eligible_service = EligibleTitlesService()
    content_service = ContentService()
    
    # Create analyzer and pipeline
    analyzer = SafeZoneAnalyzer(
        provider="openai",
        model=config.openai_model,
        api_key=config.openai_api_key,
    )
    
    try:
        # Filter SOT types if specified
        sot_types = list(sot_type) if sot_type else None
        
        click.echo(f"\n🔍 Fetching eligible titles from last {days_back} days...")
        if sot_types:
            click.echo(f"🎯 Filtering by SOT types: {', '.join(sot_types)}")
        if limit:
            click.echo(f"📊 Limit: {limit} posters")
        
        # Use the SOT pipeline which handles everything
        sot_pipeline = SOTAnalysisPipeline(
            eligible_service=eligible_service,
            content_service=content_service,
            analyzer=analyzer,
        )
        
        click.echo(f"\n🚀 Starting analysis pipeline...\n")
        
        # Run the pipeline
        results = sot_pipeline.run(
            days_back=days_back,
            sot_types=sot_types,
            batch_size=batch_size,
            limit=limit,
            resume=False,  # Don't resume for CLI
            download_images=not no_download,
            download_timeout=download_timeout,
            save_composite_images=True,  # Save composite images for dashboard
            composite_image_dir="./debug_composite_images",
        )
        
        # Convert to result dicts for output
        all_results = [r.to_dict() for r in results]
        processed = len(results)
        
        # Output results
        click.echo(f"\n✅ Completed analysis of {processed} eligible posters")
        
        # Show summary by SOT
        sot_summary = sot_pipeline.get_summary_by_sot(results)
        
        click.echo("\n📊 Results by SOT:")
        click.echo("-" * 60)
        for sot, stats in sorted(sot_summary.items()):
            total = stats["total"]
            with_elements = stats["with_key_elements"]
            pct = with_elements / total * 100 if total > 0 else 0
            click.echo(f"{sot:15} {with_elements:4}/{total:4} ({pct:5.1f}%) have elements in red zone")
        click.echo("-" * 60)
        
        # Output results
        if output:
            output_path = Path(output)
        else:
            output_path = None
        
        if json_array:
            output_data = json_lib.dumps(all_results, indent=2)
            if output_path:
                output_path.write_text(output_data)
                click.echo(f"\n💾 Results saved to: {output_path}")
                click.echo(f"📦 File size: {len(output_data)} bytes")
            else:
                click.echo(output_data)
        else:
            # NDJSON format
            lines = []
            for result in all_results:
                lines.append(json_lib.dumps(result))
            
            output_data = "\n".join(lines)
            if output_path:
                output_path.write_text(output_data)
                click.echo(f"\n💾 Results saved to: {output_path}")
                click.echo(f"📦 File size: {len(output_data)} bytes")
            else:
                click.echo(output_data)
                
    except DatabricksError as exc:
        logger.error("analyze_eligible_failed", error=str(exc))
        raise click.ClickException(str(exc)) from exc


@cli.command()
def health():
    """Run a comprehensive health check on all components."""
    from connection import get_connection_provider
    from analysis_cache import get_analysis_cache
    from monitoring import get_analysis_monitor
    import json as json_lib
    
    health_status = {
        "databricks": "unknown",
        "cache": "unknown",
        "openai": "unknown",
        "monitoring": "unknown",
        "overall": "unknown"
    }
    
    # Check Databricks connection
    try:
        provider = get_connection_provider()
        with provider.cursor() as cursor:
            cursor.execute("SELECT current_timestamp()")
            cursor.fetchone()
        health_status["databricks"] = "ok"
        logger.info("health_check_databricks_ok")
    except Exception as exc:
        health_status["databricks"] = f"failed: {exc}"
        logger.error("health_check_databricks_failed", error=str(exc))
    
    # Check cache status
    try:
        cache = get_analysis_cache()
        cache_stats = cache.get_stats()
        health_status["cache"] = f"ok (size: {cache_stats['size']}/{cache_stats['max_size']})"
        logger.info("health_check_cache_ok", stats=cache_stats)
    except Exception as exc:
        health_status["cache"] = f"failed: {exc}"
        logger.error("health_check_cache_failed", error=str(exc))
    
    # Check OpenAI configuration
    try:
        config = get_config()
        if config.openai_api_key:
            health_status["openai"] = "configured"
        else:
            health_status["openai"] = "not configured"
    except Exception as exc:
        health_status["openai"] = f"failed: {exc}"
        logger.error("health_check_openai_failed", error=str(exc))
    
    # Check monitoring status
    try:
        monitor = get_analysis_monitor()
        monitor_stats = monitor.get_health_status()
        health_status["monitoring"] = f"{monitor_stats['status']} (alerts: {len(monitor_stats['alerts'])})"
    except Exception as exc:
        health_status["monitoring"] = f"failed: {exc}"
        logger.error("health_check_monitoring_failed", error=str(exc))
    
    # Overall status
    if all(v.startswith("ok") or v == "configured" for v in health_status.values() if v != "unknown"):
        health_status["overall"] = "healthy"
    elif health_status["databricks"].startswith("ok"):
        health_status["overall"] = "partial"
    else:
        health_status["overall"] = "unhealthy"
    
    # Output result
    click.echo(json_lib.dumps(health_status, indent=2))
    
    # Exit code based on overall status
    if health_status["overall"] == "unhealthy":
        raise click.ClickException("Health check failed")


if __name__ == "__main__":
    cli()

