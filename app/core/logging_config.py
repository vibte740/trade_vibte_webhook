"""Structured logging setup."""
import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog


def setup_logging(
    log_format: str = "console",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_max_bytes: int = 10_485_760,
    log_backup_count: int = 5,
) -> None:
    """Configure structured logging for the application."""
    # Ensure log directory exists
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Shared processors for structlog
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Determine which renderer to use
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure logging with ProcessorFormatter
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": renderer,
                "foreign_pre_chain": shared_processors,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "stream": sys.stdout,
            }
        },
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
    }

    # Add file handler if specified
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "structured",
            "filename": log_file,
            "maxBytes": log_max_bytes,
            "backupCount": log_backup_count,
        }
        logging_config["root"]["handlers"].append("file")

    logging.config.dictConfig(logging_config)

    # Configure structlog to wrap records for ProcessorFormatter
    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound to the given name."""
    return structlog.get_logger(name)


def log_webhook_event(
    logger: structlog.stdlib.BoundLogger,
    event: str,
    payload: Dict[str, Any],
    **extra: Any,
) -> None:
    """Standard webhook event logging."""
    logger.info(
        event,
        ticker=payload.get("ticker"),
        action=payload.get("action"),
        quantity=payload.get("quantity"),
        **extra,
    )


def log_error(
    logger: structlog.stdlib.BoundLogger,
    error: Exception,
    context: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an error with full context."""
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context,
        payload=payload or {},
        exc_info=True,
    )
