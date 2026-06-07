import json
import logging
import sys
from typing import Any

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Custom formatter to emit clean, single-line JSON structures for aggregators."""

    def format(self, record: logging.LogRecord) -> str:
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


def get_logger(name: str, json_logs: bool = True) -> logging.Logger:
    """Create and return a logger that emits JSON-formatted logs to stdout.

    - Reuses an existing logger if already configured.
    - Respects `LOG_LEVEL` environment variable (defaults to INFO).
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    # Respect LOG_LEVEL env var
    log_level = settings.LOG_LEVEL.upper()
    try:
        level = getattr(logging, log_level)
    except Exception:
        level = logging.INFO

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    logger.addHandler(handler)
    logger.propagate = False

    return logger
