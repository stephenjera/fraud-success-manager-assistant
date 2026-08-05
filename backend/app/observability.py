"""Langfuse observability integration for the FSM Copilot.

Wires Langfuse into Pydantic-ai's native OpenTelemetry instrumentation
and provides session-scoped helpers for token tracking and metadata.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import TYPE_CHECKING

from app.config import settings
from app.logger import get_logger

if TYPE_CHECKING:
    from langfuse import Langfuse

logger = get_logger("langfuse")

_langfuse_client: Langfuse | None = None
_current_session_id: ContextVar[str | None] = ContextVar("session_id", default=None)


def _set_langfuse_env() -> None:
    """Export Langfuse env vars so the OTel exporter picks them up."""
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    if settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    if settings.LANGFUSE_BASE_URL:
        os.environ["LANGFUSE_BASE_URL"] = settings.LANGFUSE_BASE_URL


def init_langfuse() -> Langfuse | None:
    """Initialise the Langfuse client if credentials are configured.

    Returns:
        The Langfuse client, or None if Langfuse is not enabled.
    """
    global _langfuse_client

    if not settings.langfuse_enabled:
        logger.info("Langfuse not configured - observability disabled")
        return None

    if _langfuse_client is not None:
        return _langfuse_client

    try:
        # Ensure OTel exporter receives the correct config
        _set_langfuse_env()

        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL.replace("http://", "").replace("https://", "").split("/")[0],
            tracing_enabled=True,
        )
        logger.info("Langfuse client initialised")
        return _langfuse_client
    except Exception as exc:
        logger.error("Failed to initialise Langfuse: %s", exc)
        _langfuse_client = None
        return None


def get_langfuse() -> Langfuse | None:
    """Return the Langfuse client instance."""
    return _langfuse_client


def get_current_session_id() -> str | None:
    """Return the current session ID from context."""
    return _current_session_id.get()


def set_session_context(session_id: str) -> None:
    """Set the session ID for the current request context."""
    _current_session_id.set(session_id)


def reset_session_context() -> None:
    """Clear the session ID from the current context."""
    _current_session_id.set(None)


def flush_langfuse() -> None:
    """Flush buffered Langfuse events."""
    if _langfuse_client:
        try:
            _langfuse_client.flush()
        except Exception:
            pass
