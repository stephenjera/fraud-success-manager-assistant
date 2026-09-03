"""The in-process run event bus (ADR-0011).

A run is one agent turn. The *state* is durable (``appstate``); the *stream* is
a view of it. The producer is the run executor :mod:`app.services.run`; the
consumer is the ``GET /v1/runs/{id}/events`` generator. Both live in one
process, so a per-process dict of async queues is the whole transport.

Reconnect: ``Last-Event-ID`` replays from the ring buffer. A fully-terminal run
has an empty buffer + a terminal flag, so a fresh subscriber sees nothing new and
ends — the answer is re-fetched via ``GET …/messages/{mid}`` (the durable fact).
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections import deque
from typing import Any, AsyncIterator

_RING = 256  # events kept per run for Last-Event-ID replay


class Event:
    """A typed SSE event: ``event: <name>\\ndata: <json>\\n\\n``."""

    __slots__ = ("name", "payload")

    def __init__(self, name: str, payload: dict[str, Any]) -> None:
        self.name = name
        self.payload = payload

    def encode(self) -> str:
        return f"event: {self.name}\ndata: {json.dumps(self.payload, default=str)}\n\n"


class _Bus:
    """run_id → (ring buffer, live waiters, terminal flag)."""

    def __init__(self) -> None:
        self._bufs: dict[str, deque[Event]] = {}
        self._waiters: dict[str, set[asyncio.Queue[Event | None]]] = {}
        self._terminal: dict[str, bool] = {}

    def ensure(self, run_id: str) -> None:
        self._bufs.setdefault(run_id, deque(maxlen=_RING))
        self._waiters.setdefault(run_id, set())
        self._terminal.setdefault(run_id, False)

    def push(self, run_id: str, name: str, payload: dict[str, Any]) -> None:
        self.ensure(run_id)
        ev = Event(name, payload)
        self._bufs[run_id].append(ev)
        for q in self._waiters[run_id]:
            q.put_nowait(ev)

    def mark_terminal(self, run_id: str) -> None:
        self.ensure(run_id)
        self._terminal[run_id] = True
        for q in self._waiters[run_id]:
            q.put_nowait(None)  # sentinel: end of stream

    def is_terminal(self, run_id: str) -> bool:
        return self._terminal.get(run_id, False)

    def buffer(self, run_id: str) -> list[Event]:
        return list(self._bufs.get(run_id, ()))

    def subscribe(self, run_id: str) -> asyncio.Queue[Event | None]:
        self.ensure(run_id)
        q: asyncio.Queue[Event | None] = asyncio.Queue()
        self._waiters[run_id].add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[Event | None]) -> None:
        self._waiters.get(run_id, set()).discard(q)

    async def stream(self, run_id: str, last_event_id: int | None = None) -> AsyncIterator[Event]:
        """Yield buffered events (after ``last_event_id``), then live, until terminal.

        A fresh subscriber that arrives mid-run still blocks for the remaining
        live events and the terminal sentinel (``None``); the early-return that
        used to treat "no subscribers yet" as "no more events" was the race — a
        client that opened the stream after the first push and before the run
        finished would get the buffer and then a silent close, dropping the
        final events and the terminal flag.
        """
        self.ensure(run_id)
        buf = self.buffer(run_id)
        start = last_event_id if (last_event_id is not None and last_event_id < len(buf)) else 0
        for ev in buf[start:]:
            yield ev
        if self.is_terminal(run_id):
            # run is done and fully delivered to this subscriber: stop
            return
        q = self.subscribe(run_id)
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield item
        finally:
            self.unsubscribe(run_id, q)


_bus = _Bus()
_seq = itertools.count(1)


def ensure(run_id: str) -> None:
    _bus.ensure(run_id)


def push(run_id: str, name: str, payload: dict[str, Any]) -> int:
    """Emit one event; return a monotonically-increasing id (for Last-Event-ID)."""
    _bus.push(run_id, name, payload)
    next(_seq)
    return len(_bus.buffer(run_id))


def mark_terminal(run_id: str) -> None:
    _bus.mark_terminal(run_id)


def is_terminal(run_id: str) -> bool:
    return _bus.is_terminal(run_id)


def stream(run_id: str, last_event_id: int | None = None) -> AsyncIterator[Event]:
    return _bus.stream(run_id, last_event_id)


def sse_lines(run_id: str, last_event_id: int | None = None) -> AsyncIterator[str]:
    """The generator a FastAPI ``StreamingResponse`` consumes (pre-encoded SSE)."""

    async def _gen() -> AsyncIterator[str]:
        async for ev in stream(run_id, last_event_id):
            yield ev.encode()
        # keep-alive is implicit when the stream ends; the client re-fetches state.

    return _gen()
