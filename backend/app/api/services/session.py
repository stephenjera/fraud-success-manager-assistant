"""
Session + execution state tracking.

Thin wrapper around session_store.py (SQLite-backed persistence) that
preserves the original in-memory interface so callers need not change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.api.services import session_store as _store

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage


class SessionManager:
    """
    Stores conversational history used by the LLM.

    All calls are proxied to the SQLite-backed session_store.
    """

    def get_history(self, session_id: str) -> list[ModelMessage]:
        return _store.get_chat_history(session_id)

    def save_history(self, session_id: str, history: list[ModelMessage]) -> None:
        _store.save_chat_messages(session_id, history)


session_store = SessionManager()


@dataclass
class ExecutionEvent:
    sql: str
    columns: list[str] | None = None
    row_count: int | None = None
    preview_rows: list[list[Any]] | None = None
    execution_ms: float | None = None


class ExecutionStore:
    """
    Stores raw system execution traces (proxied to SQLite).
    """

    def append(self, session_id: str, event: ExecutionEvent) -> None:
        _store.append_execution_event(session_id, event)

    def get(self, session_id: str) -> list[ExecutionEvent]:
        return _store.get_execution_events(session_id)


execution_store = ExecutionStore()


class SessionFacade:
    """Abstraction layer for replay tools, debugging UI, FSM visualisation."""

    def __init__(self, chat: SessionManager, exec_store: ExecutionStore) -> None:
        self.chat = chat
        self.exec = exec_store


session_facade = SessionFacade(session_store, execution_store)
