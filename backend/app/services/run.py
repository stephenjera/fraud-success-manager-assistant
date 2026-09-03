"""Execute one agent run and emit its frozen SSE event set (ADR-0011).

Flow (the walk's step-5 event order):
  run.start → (tool_call.start, tool_call.done) ×N → message.delta → run.done|run.error.

The graph is synchronous (Ollama in-thread + psycopg tools), so it is invoked on a
worker thread (``run(...)/asyncio.to_thread`` inside the API); this module only
emits events onto the in-process bus and writes the terminal row exactly once.
The durable answer is the stored fact; the stream is only the view of it
(a dropped stream never loses the answer — ADR-0011).
"""

from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage

from app.agents.graph import create_graph
from app.common.observability import get_tracing_callbacks
from app.common.settings import settings
from app.services import events, store

_GRAPH = None


def _graph() -> Any:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = create_graph()
    return _GRAPH


class _EventEmitter(BaseCallbackHandler):
    """Tool callbacks → the contract's ``tool_call.start`` / ``tool_call.done``."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._pending: dict[Any, str] = {}

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, *, run_id: Any, **kw: Any) -> Any:
        name = (serialized or {}).get("name") or "run_sql"
        self._pending[run_id] = name
        try:
            args = json.loads(input_str) if input_str else {}
        except (ValueError, TypeError):
            args = {}
        events.push(self.run_id, "tool_call.start", {"tool": name, "args": args})

    def on_tool_end(self, output: Any, *, run_id: Any, **kw: Any) -> Any:
        name = self._pending.pop(run_id, "run_sql")
        text = output if isinstance(output, str) else str(output)
        events.push(self.run_id, "tool_call.done", {"tool": name, "result_summary": text[:200]})


def _tokens(messages: list[Any] | None) -> tuple[int, int]:
    """Best-effort (in, out) token counts from the last AIMessage usage (0 if absent)."""
    for m in reversed(messages or []):
        usage = getattr(m, "usage_metadata", None)
        if usage:
            return int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)
    return 0, 0


def execute(conversation_id: str, message_id: str, run_id: str, text: str) -> None:
    """Run the agent once; push events and persist the terminal state.

    Called on a worker thread. Never raises — a failure is a *result*
    (``run.error`` + a ``status='error'`` row), not a crash.
    """
    events.ensure(run_id)
    start = time.monotonic()
    events.push(run_id, "run.start", {"run_id": run_id, "model": settings.llm_model, "schema_version": "1"})
    emitter = _EventEmitter(run_id)
    config: dict[str, Any] = {
        "recursion_limit": 25,
        "configurable": {"thread_id": run_id},
        "callbacks": [emitter, *get_tracing_callbacks()],
    }
    try:
        result = _graph().invoke({"messages": [HumanMessage(content=text)]}, config)
    except Exception as exc:  # noqa: BLE001 - a run failure is a result, not a crash
        _fail(run_id, message_id, start, str(exc))
        return

    grounding = result.get("grounding") if isinstance(result, dict) else None
    if not grounding:
        _fail(run_id, message_id, start, "The agent did not produce a grounded answer.")
        return

    events.push(run_id, "message.delta", {"delta": grounding.get("explanation", "")})
    tokens_in, tokens_out = _tokens(result.get("messages"))
    events.push(run_id, "run.done", {
        "message_id": message_id,
        "duration_ms": int((time.monotonic() - start) * 1000),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    })
    events.mark_terminal(run_id)
    store.set_result(
        run_id,
        message_id,
        success=True,
        status="success",
        grounding=grounding,
        error=None,
        sql=grounding.get("sql"),
        sql_preview=store.revision_preview(grounding.get("sql", "")),
    )


def _fail(run_id: str, message_id: str, start: float, detail: str) -> None:
    events.push(run_id, "run.error", {
        "code": "LLM_ERROR",
        "message": "The agent turn failed.",
        "details": {"error": detail},
    })
    events.mark_terminal(run_id)
    store.set_result(
        run_id,
        message_id,
        success=False,
        status="error",
        grounding=None,
        error={"code": "LLM_ERROR", "message": "The agent turn failed.", "details": {"error": detail}},
        sql=None,
        sql_preview="",
    )
