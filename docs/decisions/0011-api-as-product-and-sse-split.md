# ADR-0011 — API as a complete product; SSE command/query split

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

We are building a frontend that consumes a backend. The open question was
how hard to build the API as a self-sufficient product — the "the backend
is the product and the frontend is one consumer" stance — versus a
coupled MVP API.

## Decision

**The API is the product. The reference frontend in this repo is its first
consumer.** Consequences that follow:

- Everything the UI needs is data or an event; nothing that needs to be
  *rendered by the client* is baked into the API.
- The contract is frozen *before* the frontend is built
  (`docs/architecture/api-contract.md`). The frontend is the reference
  implementation, not a co-author of the contract.
- **SSE uses a command/query split (CQRS-lite).**
  `POST /v1/conversations/{id}/messages` is a **command**: it durably
  creates the message and *starts* the run, returns
  `201 {message, run_id}` immediately. The stream is a **view** of the
  durable state: `GET /v1/runs/{run_id}/events` (SSE), reconnectable by
  `Last-Event-ID`. A dropped stream does not lose the answer — the
  answer was stored by the command. Any client (browser, curl, another
  service) can GET the message, poll the run, or attach to the stream
  without a different code path.
- All routes are versioned under `/v1/`. A live GenAI contract will
  change; `/v1/` is one path segment now vs. a rewrite later.
- `DELETE` endpoints exist for `conversations` / `insights` / `rules`.
  We aim at prod standards from day one; skipping them for a one-user
  prototype would be a knowledge gap, not a save.
- Lists use an envelope (`{items, page, page_size?, token?}`) and every
  error is `{error: {code, message, details?}}` with a stable `code`
  string. Cheap now; the only ways to grow past "100 rows" without a
  breaking change.

## Alternatives considered

- **One endpoint, POST returns the full assembled answer synchronously.**
  Rejected. This is the "MVP lazy path." It's also the only thing in this
  design that would make the spec's own "transparency of reasoning"
  value-prop (§6.5) *impossible*: with no command/query split, the one
  channel (a long-lived `POST` response) is the single point of failure
  for any client that has to reconnect.
- **No `/v1/`** (ponytail). Rejected on the same grounds as the
  command/query split: the cost is one segment, the savings are a
  1000-line rewrite in P3.
- **No DELETE** (YAGNI). Rejected: a one-user prototype with a full
  resource lifecycle is the *point* of the rule state machine; the
  `DELETE` endpoint costs a line and prevents the "why does this not
  exist" question in P3.

## Consequences

- `201` semantics + `run_id` in the response = a contract that
  *naturally* supports the `202`/`201` split the SSE design needs.
- The `runs` resource is now a first-class *readable* thing that isn't a
  write side effect (any client can `GET /v1/runs/{id}` without a
  `POST`); the agent-loop checkpoint (ADR-0003) is what *backs* the run
  state, not a separate store.
- The state machine (`core/rule_state.py`) gains a read surface —
  `rule.status` and `rule.last_changed_by` are part of the rule object,
  so `PATCH` and the lifecycle verbs share one source of truth.
- Any client written against this contract (not just the reference
  frontend) can run the full lifecycle: ask → stream → pin → draft →
  backtest → approve → deploy, without touching application code.
