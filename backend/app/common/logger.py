"""Structured JSON logging to stdout."""

import json
import logging
import sys
from typing import Any

from app.common.settings import settings


class JSONFormatter(logging.Formatter):
    """Emit clean, single-line JSON log records for aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialise a log record to a single JSON line."""
        log: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
            "message": record.getMessage(),
        }
        return json.dumps(log)


def get_logger(name: str, *, json_logs: bool = True) -> logging.Logger:
    """Create and return a logger that emits JSON-formatted logs to stdout.

    - Reuses an existing logger if already configured.
    - Honours the ``log_level`` setting (defaults to INFO).
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    # Respect the configured log level
    log_level = settings.log_level.upper()
    try:
        level = getattr(logging, log_level)
    except AttributeError:
        level = logging.INFO

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        plain = "%(asctime)s %(levelname)s %(name)s %(message)s"
        handler.setFormatter(logging.Formatter(plain))

    logger.addHandler(handler)
    logger.propagate = False

    return logger
