# ADR-0016 — MemorySaver is sufficient; PostgresSaver not needed

**Status:** accepted (2026-09-04)
**Date:** 2026-09-04
**Supersedes:** ADR-0013 "PostgresSaver deferred to P2" (the deferral path is closed).

## Context

ADR-0013 deferred `PostgresSaver` wiring to P2 on the grounds that the rule lifecycle would benefit from checkpoint durability. P2 is done, but `PostgresSaver` was never wired — the graph uses LangGraph's default in-memory `MemorySaver`.

Two facts make `PostgresSaver` unnecessary for this project:

1. **The durable state is `appstate`, not the checkpoint.** ADR-0011 (API-as-product, SSE split) mandates that `services/` writes the `grounding` payload to `appstate.messages` before the stream closes. The SSE stream is a *view* of that row, not the checkpoint. A client that lost its stream reconnects via `GET /v1/runs/{id}` + `GET /v1/conversations/{id}/messages/{mid}` — not via the checkpoint tables.

2. **Single user, single process.** This is a local reference implementation with one operator. There is no multi-user deployment, no hot reload during a run, no horizontally scaled agent pool. The checkpoint's job is intra-run state persistence, which `MemorySaver` covers.

The architecture docs (`agent-loop.md`, `components.md`, `data-model.md`) still reference `PostgresSaver` as if it were wired. Those references are incorrect — the graph uses `MemorySaver`.

## Decision

**Formally reject `PostgresSaver`.** The decision is "not now" has aged to "not for this project." The in-memory checkpointer is sufficient; `appstate` rows are the durable record. The `langgraph-checkpoint-postgres` dependency remains in `pyproject.toml` (it is installed, harmless, and provides the checkpoint DB schema if a future deployment needs it), but the graph does not wire it.

## Consequences

- `agent-loop.md` checkpointing section is updated to state `MemorySaver` is the actual back-end, and the "resume" claim from ADR-0011 is satisfied by the durable `appstate` row, not the checkpoint.
- `components.md` is updated: `services/` no longer constructs a `PostgresSaver`.
- `data-model.md` is updated: the checkpoint tables are not created by Alembic (they're not needed).
- ADR-0013's deferral is closed — no future phase owes this work.

## Alternatives considered

- **Wire it "just in case."** It is a non-trivial integration (connection pooling, `app_rw` lease, Alembic migration for checkpoint tables) for a property this project doesn't need. The dependency already exists in the lockfile, so the *option* is preserved without the integration cost.

- **Keep deferring.** A deferral past P2 with P3 built and working on `MemorySaver` is a decision deferred into rot. This ADR closes the path explicitly.
