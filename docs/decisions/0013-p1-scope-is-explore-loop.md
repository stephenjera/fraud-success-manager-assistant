# ADR-0013 — P1 scope is the explore loop; rule lifecycle and PostgresSaver defer to P2

**Status:** accepted (2026-09-03, after P1 implementation)
**Date:** 2026-09-03

## Context

The P0 freeze (`P1-reliable-nl-to-sql-and-proof.md` DoD) listed two items that
turn out to be P2 scope, not P1:

1. **The headless E2E walkthrough** (`DoD item 4`) originally described "the
   full FSM workflow — explore → rerun → pin → draft → backtest → approve →
   deploy → catalog". Phases 4-7 of `e2e-walktalk.md` (pin, draft, backtest,
   approve, deploy, catalog) live in the rule-lifecycle engine that P2 builds.
   Only Phases 1-3 (session start, first grounded turn, edit + re-run) are P1.

2. **`langgraph-checkpoint-postgres`** was installed at P0 but never wired.
   `create_graph()` uses the in-memory `MemorySaver` checkpointer (LangGraph
   default). The in-memory checkpointer is sufficient for P1's use case
   (single-process, single-thread-per-run, no multi-user persistence across
   restarts). Postgres checkpointing adds durability and cross-process
   consistency that P2's rule lifecycle will need (a pinned insight's
   backtest history should survive a redeploy) but not P1.

## Decision

- **P1 = explore loop only.** The deliverable is a working, testable,
  proven NL→SQL→grounding loop with the full P1 API surface
  (`/v1/conversations`, `/v1/runs`, `/v1/meta`, `rerun`, `revisions`),
  the SSE event bus, the three-layer wall, and the `tests/test_api.py`
  + `tests/test_events.py` + `tests/test_architecture.py` proof.
  `scripts/e2e_walktalk.py` walks **Phases 1-3 only** (the `make e2e` member).
  Phases 4-7 are a P2 deliverable.

- **PostgresSaver deferred.** `create_graph()` keeps the in-memory checkpointer
  for P1. Wiring `AsyncPostgresSaver` (or the sync `PostgresSaver`) is a
  P2 task, alongside the rule-engine state that benefits from it. The
  `langgraph-checkpoint-postgres` dependency stays in `pyproject.toml`
  (already installed) so the P2 wiring is a pure config change.

## Consequences

- The P1 phase doc DoD is updated: item 4 says Phases 1-3, not the full walk.
- `backend/scripts/e2e_walktalk.py` (when written) asserts Phases 1-3 shapes
  only and is a `make e2e` member (not `make eval` with promptfoo, which is
  a P4 hardening item).
- P2's first infra task is the PostgresSaver swap, not a new dependency.
- In-memory checkpointer means `conversations`/`runs` in Postgres are the
  durable state; the LangGraph checkpoint is ephemeral per-run. This is
  consistent with the existing ADR-0011 command/query split: the durable
  fact is the `appstate` row, the in-memory checkpoint is just the loop state.
