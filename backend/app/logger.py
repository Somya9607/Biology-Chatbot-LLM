"""Structured logging setup using structlog.

Emits JSON log lines to both the console and a dated file
(``{LOG_DIR}/biology_rag_{date}.jsonl``). Every entry carries an ISO-8601
timestamp, log level, the event name and any contextual key/value fields
passed at the call site.

Usage::

    from app.logger import get_logger
    log = get_logger(__name__)
    log.info("ingestion.extract", filename="x.pdf", total_pages=210)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import structlog

from app.config import settings

_CONFIGURED = False


def _ensure_log_dir() -> Path:
    """Create the log directory if needed and return today's log file path."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return log_dir / f"biology_rag_{date_str}.jsonl"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog + stdlib logging once for the whole process.

    Args:
        level: Minimum stdlib log level (DEBUG/INFO/WARNING/ERROR).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_file = _ensure_log_dir()

    # JSON renderer shared by console and file handlers.
    json_renderer = structlog.processors.JSONRenderer()

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=json_renderer,
        foreign_pre_chain=shared_processors,
    )

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if reconfigured (e.g. under --reload).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger, configuring on first use."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name or "biology_rag")
