"""Runs — the streaming view (ADR-0011): the durable status object and the SSE log.

``GET /v1/runs/{id}`` returns the small durable object; ``GET /v1/runs/{id}/events``
streams the frozen event set as ``text/event-stream``. Reconnect by ``Last-Event-ID``
replays from the in-process buffer; a terminal run replays and ends — the answer is
re-fetched via the message DTO (the durable fact), never the stream.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api import errors
from app.services import events, store

router = APIRouter(prefix="/v1/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    """The run's durable status object (small, always readable)."""
    run = store.get_run(run_id)
    if run is None:
        raise errors.not_found(f"Run {run_id!r} not found.")
    return run


@router.get("/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    """Stream the run's events (``text/event-stream``); reconnect via ``Last-Event-ID``."""
    if store.get_run(run_id) is None:
        raise errors.not_found(f"Run {run_id!r} not found.")
    last = request.headers.get("Last-Event-ID") or request.headers.get("Last-Event-Id")
    last_int = int(last) if last and last.isdigit() else None
    return StreamingResponse(
        _sse(run_id, last_int),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


async def _sse(run_id: str, last: int | None) -> AsyncIterator[str]:
    """The pre-encoded SSE frames a ``StreamingResponse`` consumes."""
    async for line in events.sse_lines(run_id, last):
        yield line
