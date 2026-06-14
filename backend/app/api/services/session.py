"""
In-memory session + execution state tracking (MVP version).

We separate:
1. Chat history (LLM-facing memory)
2. Execution logs (system telemetry, NOT LLM input)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage


class SessionManager:
    """
    Stores conversational history used by the LLM.

    ONLY contains:
    - user messages
    - assistant messages
    - tool messages (if applicable)

    NEVER contains:
    - SQL execution results
    - metrics
    - system telemetry
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[ModelMessage]] = {}

    def get_history(self, session_id: str) -> list[ModelMessage]:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]

    def save_history(self, session_id: str, history: list[ModelMessage]) -> None:
        self._sessions[session_id] = history


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
    Stores raw system execution traces.

    This is:
    - NOT passed to LLM
    - used for debugging, replay, analytics, evaluation
    """

    def __init__(self) -> None:
        self._logs: dict[str, list[ExecutionEvent]] = {}

    def append(self, session_id: str, event: ExecutionEvent) -> None:
        if session_id not in self._logs:
            self._logs[session_id] = []
        self._logs[session_id].append(event)

    def get(self, session_id: str) -> list[ExecutionEvent]:
        return self._logs.get(session_id, [])


execution_store = ExecutionStore()


class SessionFacade:
    """
    Optional abstraction layer for future:
    - replay tools
    - debugging UI
    - FSM visualization
    """

    def __init__(self, chat: SessionManager, exec_store: ExecutionStore) -> None:
        self.chat = chat
        self.exec = exec_store


session_facade = SessionFacade(session_store, execution_store)
