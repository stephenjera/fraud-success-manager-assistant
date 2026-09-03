"""Regression for the ``events`` bus: a fresh subscriber must get every event
and the terminal sentinel, even when the producer is already running.

The bug this locks in: ``stream()`` used to early-return when it saw
"not terminal AND no subscribers yet" — so a client that opened the SSE stream
*after* the first push and *before* the run finished got its partial buffer,
then a silent close, dropping the remaining events and the terminal flag.
Each test drives producer + subscriber concurrently on one loop (the shape the
``GET /runs/{id}/events`` route uses for a mid-run client).
"""

from __future__ import annotations

import asyncio

from app.services import events


def _run(coro, timeout: float = 2.0):
    """Drive a coroutine to completion on a fresh loop; fail (not hang) on timeout."""
    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


async def _producer(run_id: str, gap: float) -> None:
    """Push run.start → gap → message.delta → gap → run.done → terminal."""
    events.push(run_id, "run.start", {"run_id": run_id})
    await asyncio.sleep(gap)
    events.push(run_id, "message.delta", {"delta": "partial"})
    await asyncio.sleep(gap)
    events.push(run_id, "run.done", {"message_id": "m"})
    events.mark_terminal(run_id)


class TestStreamRace:
    def test_fresh_subscriber_mid_run_gets_every_event(self) -> None:
        """Consumer attaches after run.start is pushed but before terminal.

        It must read the buffered event AND keep waiting for the live ones —
        the old early-return would have returned only the partial buffer and
        closed, so this assertion is the regression guard."""
        run_id = "race-fresh"
        gap = 0.06  # producer: run.start @0, delta @0.06, done+terminal @0.12

        async def drive() -> list[str]:
            producer = asyncio.ensure_future(_producer(run_id, gap))
            await asyncio.sleep(gap / 2)  # t=0.03: run.start buffered, run not done
            got: list[str] = []
            async for ev in events.stream(run_id):
                got.append(ev.name)
            await producer
            return got

        assert _run(drive()) == ["run.start", "message.delta", "run.done"]

    def test_subscriber_after_terminal_replays_and_ends(self) -> None:
        """Consumer arrives after the run is fully terminal: full replay, then end."""
        run_id = "race-terminal"

        async def drive() -> list[str]:
            await _producer(run_id, gap=0.01)  # producer fully done before subscribe
            got: list[str] = []
            async for ev in events.stream(run_id):
                got.append(ev.name)
            return got

        assert _run(drive()) == ["run.start", "message.delta", "run.done"]

    def test_last_event_id_replay_skips_prefix(self) -> None:
        """Reconnect with ``last_event_id``: events before that buffer index are
        skipped; the run is terminal so only the replay is seen."""
        run_id = "race-replay"

        async def drive() -> list[str]:
            await _producer(run_id, gap=0.01)
            got: list[str] = []
            async for ev in events.stream(run_id, last_event_id=1):
                got.append(ev.name)
            return got

        assert _run(drive()) == ["message.delta", "run.done"]
