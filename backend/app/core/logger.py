import json
import logging
import sys
import os
from typing import Any
from contextvars import ContextVar


class JSONFormatter(logging.Formatter):
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

        # Optional: include request_id if present
        if hasattr(record, "request_id"):
            log["request_id"] = record.request_id

        return json.dumps(log)


# Context var for per-request ids (FastAPI middleware will set/reset this)
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - simple passthrough
        # Attach request_id from context var when available
        try:
            record.request_id = request_id_ctx.get()
        except Exception:
            record.request_id = None

        return True


try:
    from colorlog import ColoredFormatter

    colour_formatter: Any = ColoredFormatter(
        "%(log_color)s[%(asctime)s] [%(levelname)s] [%(name)s] "
        "[%(filename)s:%(lineno)d - %(funcName)s()]%(reset)s %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
except ImportError:
    colour_formatter = None


standard_formatter = (
    "[%(asctime)s] [%(levelname)s] [%(name)s] "
    "[%(filename)s:%(lineno)d - %(funcName)s()] %(message)s"
)
STANDARD_FORMATTER = logging.Formatter(standard_formatter)


def get_logger(name: str, json_logs: bool = True) -> logging.Logger:
    """Create a production-ready logger with file, line, function, and optional JSON output."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    # Allow override via LOG_LEVEL env var (e.g. LOG_LEVEL=DEBUG)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    try:
        level = getattr(logging, log_level)
    except Exception:
        level = logging.INFO

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)

    # Attach request-id filter so any request-specific id set in context is included
    handler.addFilter(RequestIDFilter())

    if json_logs:
        handler.setFormatter(JSONFormatter())
    elif colour_formatter:
        handler.setFormatter(colour_formatter)
    else:
        handler.setFormatter(STANDARD_FORMATTER)

    logger.addHandler(handler)
    logger.propagate = False

    return logger
