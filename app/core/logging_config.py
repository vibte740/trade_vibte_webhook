"""Structured logging setup."""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import structlog
from python_json_logger import json_logger


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

    if log_format == "json":
        # JSON logging (ideal for production/cloud)
        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.JSONRenderer(),
                    "foreign_pre_chain": shared_processors,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": sys.stdout,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
        }
        if log_file:
            logging_config["handlers"]["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": log_file,
                "maxBytes": log_max_bytes,
                "backupCount": log_backup_count,
            }
            logging_config["root"]["handlers"].append("file")

        logging.config.dictConfig(logging_config)
        structlog.configure(
            processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Human-readable console logging (dev/CI)
        structlog.configure(
            processors=shared_processors
            + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, log_level.upper()),
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
        "webhook_event",
        event=event,
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
