"""Structured logging using ``structlog`` with JSON output in production.

The output is a single line of JSON per event in production, pretty
console rendering in development, and is suitable for shipping to
ELK / Loki / Datadog / Cloud Logging.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars
from structlog.dev import ConsoleRenderer
from structlog.processors import (
    JSONRenderer,
    TimeStamper,
    add_log_level,
    format_exc_info,
)
from structlog.stdlib import BoundLogger, ProcessorFormatter
from structlog.types import EventDict, Processor

from app.settings import LogFormat, Settings, get_settings

__all__ = [
    "bind_contextvars",
    "clear_contextvars",
    "configure_logging",
    "get_logger",
    "logger",
]


def _add_severity(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Map stdlib log levels to GCP ``severity`` field names."""
    mapping = {
        "debug": "DEBUG",
        "info": "INFO",
        "warning": "WARNING",
        "warn": "WARNING",
        "error": "ERROR",
        "critical": "CRITICAL",
        "fatal": "CRITICAL",
    }
    level = event_dict.get("level", "info")
    event_dict["severity"] = mapping.get(level.lower() if isinstance(level, str) else "info", "INFO")
    return event_dict


def _add_service_info(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    settings = get_settings()
    event_dict.setdefault("service", settings.app_name)
    event_dict.setdefault("service_version", settings.app_version)
    event_dict.setdefault("env", settings.app_env.value)
    return event_dict


def configure_logging(settings: Settings | None = None) -> None:
    """Initialise structlog + stdlib logging.

    Call once from the FastAPI lifespan and once from the Celery worker
    ``on_startup`` signal.
    """
    cfg = settings or get_settings()

    level = getattr(logging, cfg.logging.level.upper(), logging.INFO)
    timestamper = TimeStamper(fmt="iso", utc=True, key="timestamp")

    shared_processors: list[Processor] = [
        merge_contextvars,
        structlog.stdlib.add_logger_name,
        add_log_level,
        timestamper,
        _add_service_info,
        format_exc_info,
    ]

    if cfg.logging.format == LogFormat.JSON:
        renderer: Processor = JSONRenderer(sort_keys=True)
    else:
        renderer = ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter_settings: dict[str, Any] = {
        "processors": [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _add_severity,
            renderer,
        ],
        "foreign_pre_chain": shared_processors,
    }

    handlers: dict[str, dict[str, Any]] = {
        "default": {
            "level": level,
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stderr",
        },
    }

    if cfg.logging.file:
        log_path = Path(cfg.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "level": level,
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(log_path),
            "maxBytes": 50 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        }

    loggers: dict[str, dict[str, Any]] = {
        "uvicorn": {"handlers": ["default"], "level": level, "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": level, "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": level, "propagate": False},
        "sqlalchemy.engine": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["default"], "level": level, "propagate": False},
        "": {"handlers": ["default"], "level": level},
    }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"()": ProcessorFormatter, **formatter_settings}},
            "handlers": handlers,
            "loggers": loggers,
        }
    )

    # Quieter noisy third-parties
    for noisy in ("httpx", "httpcore", "urllib3", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)  # type: ignore[return-value]


# Module-level convenience logger
logger: BoundLogger = get_logger("docconverter")
