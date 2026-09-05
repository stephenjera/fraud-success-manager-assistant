# ADR-0017: P6 scope — full frontend redesign plus the backend error-contract fixes

**Status:** accepted (2026-09-05, after P6 implementation)
**Date:** 2026-07-21
**Supersedes:** (none)

## Context

P5 shipped a working explore → pin → draft → backtest → deploy loop, and the
2026-09 FSM evaluation (`docs/ux/fsm-evaluation-findings.md`) walked the whole
loop live. The loop works, but the evaluation produced 15 findings. Three are
genuine backend contract defects:

- Every 500 response lacks CORS headers, so in the browser they arrive as
  `ERR_FAILED` with no body (FastAPI 0.141.1 / Starlette 1.6.0: unhandled
  exceptions are rendered by `ServerErrorMiddleware`, which wraps *outside*
  `CORSMiddleware`).
- Unparseable SQL and non-UUID identifiers return 500 `INTERNAL_ERROR` with
  library internals in the body, when they are client mistakes (4xx).
- `draft-rule` happily creates a detection rule whose clause is
  `fl.is_fraud = 1` (the outcome column) — precision 1.0 in backtest, useless
  in production.

The remaining findings are frontend: state lost on refresh, a drawer that
won't open, a pinned-UI that can't edit the clause, a "New chat" that deletes
insights, stale results staying visible, and an error copy that tells the FSM
nothing. The evaluation verdict: the backend API surface is broader and more
correct than the UI uses — the UI was never rebuilt to match it.

P5 is done, but the frontend remains "very good in the API, bad in the shell"
— the P3 chaos report (`P3-frontend-chaos-report.md`) established the baseline
that the frontend is a wrapper over the API's capabilities, and P6's job is to
close the gap between what the API offers and what the UI actually uses.

## Decision

P6 is one phase with two plans, executed in order (P6a, then P6b):

1. **P6a — backend error-contract fixes** (small, testable, no new deps):
   - 500 responses carry the same CORS headers as 4xx, and never leak
     exception text.
   - Client mistakes are 4xx: unparseable SQL → 400 `SQL_REJECTED`;
     non-UUID ids → 404 `STATE_NOT_FOUND`.
   - A rule clause referencing a label column (`is_fraud`) is rejected at
     `core/rules.py` — `draft-rule` and pin both refuse with 400
     `SQL_REJECTED`; no rule row is created.
2. **P6b — frontend redesign** (full redesign, user-confirmed scope):
   - A conversations rail + conversation panel replace the top-bar view
     switch; a refresh restores the session; "New chat" does not destroy
     pins or rules.
   - One rule workspace (drawer) that opens in *every* rule status, with the
     WHERE-clause editor (the `PATCH /v1/rules/{id}` the API already
     promises), backtest detail, approve/deploy actions, and the rationale +
     assumptions the agent produced.
   - All UI state is API-hydrated: conversations, insights, rules, and
     backtests come from the API; the client holds no persistent state of its
     own.
   - Error surfacing uses the error contract: show `error.message`,
     `details.offending_sql`, and an actionable retry.
   - `API_BASE` is derived from the page origin, with the dev fallback kept
     for local runs.

## Consequences

- The error contract becomes testable per endpoint (each 4xx/5xx shape is a
  test assertion), and the browser finally receives the diagnostic it needs.
- `draft-rule` becomes a gate, not a formality: a circular clause is refused
  instead of backtested to a misleading 1.0 precision.
- The frontend is replaced, not patched: `src/features/` is restructured
  around the three panes (conversations, conversation, rule workspace), and
  the catalog view disappears into the rule workspace's "all rules" scope.
- P6b depends on P6a's error contract and validated pin/draft; P6a is small
  enough to land first in a single focused pass.
- No new backend dependencies; the frontend keeps its existing toolchain
  (Vite + React — no automated frontend test runner; after build the
  frontend is verified by an interactive LLM-Playwright session plus a
  chaos pass).

## Alternatives

- **Patch the existing frontend instead of redesigning** — rejected: most of
  the 15 findings live in the shell (state, layout, drawer, error copy);
  patching keeps the known-bad architecture.
- **A separate P6.5 "error contract" phase** — rejected: the fixes are small
  and P6b's error UI depends on them; one phase keeps the DoD coherent.
- **Client-side SQL validation only** — rejected: the pin endpoint would
  still accept `THIS IS NOT SQL` (finding #11); the server must be the gate.
