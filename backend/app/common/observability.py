"""LLM observability: Langfuse tracing behind a single swappable seam.

The rest of the codebase interacts with tracing only through the functions in
this module, so swapping Langfuse for another backend later means editing one
file. Conversation-scoped traces are tagged per run by passing
``metadata={"langfuse_session_id": <conversation_id>}`` in the LangGraph run
config — no global state.

When Langfuse is not configured, every function degrades to a no-op so local
development works without it.
"""

from __future__ import annotations

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from app.common.logger import get_logger
from app.common.settings import settings

logger = get_logger("observability")

_client: Langfuse | None = None


def is_configured() -> bool:
    """Return True when both Langfuse keys are set."""
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def get_client() -> Langfuse | None:
    """Return the shared Langfuse client, initialising it lazily.

    Returns:
        The Langfuse client, or None when Langfuse is not configured.
    """
    global _client  # noqa: PLW0603
    if _client is None and is_configured():
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url or "http://localhost:3000",
        )
        logger.info("Langfuse client initialised")
    return _client


def get_tracing_callbacks() -> list[CallbackHandler]:
    """Return LangChain-compatible callbacks to attach to any graph run.

    Usage: ``graph.invoke(state, config={"callbacks": get_tracing_callbacks()})``

    Returns an empty list when Langfuse is not configured.
    """
    if not is_configured():
        return []
    get_client()
    return [CallbackHandler(public_key=settings.langfuse_public_key)]


def check_connection() -> bool:
    """Ping Langfuse with the configured keys. Returns True/False, never raises."""
    client = get_client()
    if client is None:
        return False
    try:
        return bool(client.auth_check())
    except Exception:
        logger.exception("Langfuse connection check failed")
        return False


def flush() -> None:
    """Flush buffered trace events (call on application shutdown)."""
    client = get_client()
    if client is not None:
        try:
            client.flush()
        except Exception:
            logger.warning("Failed to flush Langfuse events", exc_info=True)
