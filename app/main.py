"""Application entrypoint with CLI."""
import os
import sys
import uvicorn
from importlib import metadata

import click
import structlog

from app.core.config import get_settings
from app.core.logging_config import setup_logging

logger = structlog.get_logger(__name__)


def run_server(host: str, port: int, workers: int, reload: bool = False):
    """Run the FastAPI server."""
    settings = get_settings()

    # Configure logging before anything else
    setup_logging(
        log_format=settings.log_format,
        log_level=settings.log_level,
        log_file=settings.log_file,
    )

    logger.info(
        "starting_server",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        dry_run=settings.dry_run,
        broker=settings.broker,
    )

    uvicorn.run(
        "app.api.webhook:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_level=settings.log_level.lower(),
        access_log=True,
    )


@click.group()
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode")
def cli(debug: bool):
    """TradingView Webhook Listener CLI."""
    if debug:
        os.environ["LOG_LEVEL"] = "DEBUG"


@cli.command()
@click.option("--host", default=None, help="Host to bind")
@click.option("--port", default=None, type=int, help="Port to bind")
@click.option("--workers", default=None, type=int, help="Number of workers")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload")
def serve(host, port, workers, reload):
    """Start the webhook server."""
    settings = get_settings()
    host = host or settings.host
    port = port or settings.port
    workers = workers or settings.workers
    run_server(host, port, workers, reload)


@cli.command()
def version():
    """Print application version."""
    try:
        version = metadata.version("trade-vibte-webhook")
    except Exception:
        version = "0.1.0-dev"
    click.echo(f"TradingView Webhook Listener v{version}")


@cli.command()
@click.option("--output", help="Output path for generated sample .env file")
def genenv(output):
    """Generate a sample .env file."""
    from app.core.config import Settings

    sample = Settings(webhook_secret="CHANGE_ME_USE_OS_URANDOM")
    lines = []
    for field_name, field in Settings.model_fields.items():
        if field.alias:
            value = getattr(sample, field_name)
            if value is None:
                value = ""
            lines.append(f"{field.alias}={value}")
    content = "\n".join(lines) + "\n"

    if output:
        with open(output, "w") as f:
            f.write(content)
        click.echo(f"Written to {output}")
    else:
        click.echo(content)


def main():
    """Main entrypoint."""
    try:
        cli()
    except KeyboardInterrupt:
        logger.info("shutting_down")
        sys.exit(0)
    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
