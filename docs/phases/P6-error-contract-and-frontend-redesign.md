# P6 — Error-contract fixes + frontend redesign

**Status:** done (2026-09-05, ADR-0017)
**Depends on:** P5 (done)

**P6a:** per-task TDD plan in
`P6a-backend-fixes-implementation.md`.

**P6b:** per-task build plan in
`P6b-frontend-redesign-implementation.md`. The scope table (B1–B10)
and the findings → fix map in this doc are the acceptance criteria;
the plan file is the task order + file-level steps. Verification is
the interactive session + chaos pass described in **Order**.

## Context

The 2026-09 FSM evaluation (`docs/ux/fsm-evaluation-findings.md`) walked the
full explore → pin → draft → backtest → deploy loop live and produced 15
findings. Three are backend contract defects (500s without CORS, client
mistakes returning 500 with internals leaked, a circular `is_fraud = 1` clause
accepted by `draft-rule`); the rest are frontend shell defects (state lost on
refresh, drawer that won't open, no clause editor, destructive "New chat",
stale results, opaque errors).

P6 fixes the contract first (P6a — small, fully testable), then rebuilds the
frontend on top of that contract (P6b — full redesign, user-confirmed).

## Scope

**P6a (backend)** — error semantics + rule gates:

| # | Fix |
|---|-----|
| A1 | 500 responses carry CORS headers (allowed origin) and no exception text |
| A2 | Unparseable SQL → 400 `SQL_REJECTED` (was 500 with sqlglot text leaked) |
| A3 | Non-UUID ids → 404 `STATE_NOT_FOUND` (was 500 with psycopg text leaked) |
| A4 | `validate_where_clause` rejects label columns (`is_fraud`) |
| A5 | `draft-rule` on a circular clause → 400 `SQL_REJECTED`, **no rule row created** |
| A6 | Pin with invalid SQL → 400 `SQL_REJECTED` (was 201) |

**P6b (frontend)** — full redesign of `src/features/` + shell:

| # | Fix |
|---|-----|
| B1 | `API_BASE` from page origin (dev fallback kept) |
| B2 | Three-pane IA: conversations rail | conversation panel | rule workspace |
| B3 | Refresh restores session (conversations from API, selected one persisted in the URL) |
| B4 | "New chat" is non-destructive (pins/rules survive; they belong to the conversation) |
| B5 | Rule workspace drawer opens in every status; re-clicking always works |
| B6 | WHERE-clause editor wired to `PATCH /v1/rules/{id}` with the rationale + assumptions shown |
| B7 | Backtest detail (precision / recall / FPR / lift + stability) with plain-English copy |
| B8 | Stale-result marking: a failed re-run marks the previous result, never hides it silently; error banner clears on reset |
| B9 | Error surfacing from the error contract: `error.message` + `details.offending_sql` + actionable retry |
| B10 | Auto-follow: the workspace shows the newest grounded message, labeled current vs stale |

## Out of scope

- New backend features (no new endpoints; `PATCH /v1/rules/{id}` already
  exists and is now actually usable).
- Authentication, multi-user, deployment tooling.
- New frontend test tooling. P6b is verified after the build by an
  interactive session — LLM driving the browser (Playwright) against the
  running app, asserting the B-checklist below — followed by a chaos pass.
  Same method that produced `../ux/fsm-evaluation-findings.md` (see
  `P3-frontend-chaos-report.md` for the precedent).

## Findings → fix map

| Finding | Fix |
|---------|-----|
| #1 drawer won't reopen | B5 |
| #2 re-run error useless | A2 + B9 |
| #3 500 for bad SQL / bad UUID | A2 + A3 |
| #4 500s lack CORS (root cause) | A1 |
| #5 "Unnamed rule" titles | B6 (backend already prefers the model's `rule_title`, P5 — UI must render it) |
| #6 refresh wipes state | B3 |
| #7 stale results + lingering banner | B8 |
| #8 hardcoded API_BASE | B1 |
| #9 weak deployed stats | B7 |
| #10 error copy non-actionable | B9 |
| #11 pin accepts non-SQL | A6 + B9 |
| #12 workspace doesn't follow turns | B10 |
| #13 `is_fraud` clause + no editor | A4 + A5 + B6 |
| #14 drawer won't open after backtest | B5 |
| #15 "New chat" destroys insights | B4 |

## Definition of done (verifiable, not a mood)

P6a —

- [x] `pytest tests/test_errors.py` passes: a 500 with an allowed `Origin`
      returns `access-control-allow-origin` +
      `access-control-allow-credentials: true`; a disallowed origin does not;
      the body never contains the exception text.
- [x] `GET /v1/conversations/not-a-uuid` → 404 `STATE_NOT_FOUND`; no
      "invalid input syntax" in the body.
- [x] `validate_sql("SELEC * FROM transactionz")` raises `SqlRejected`
      (400 `SQL_REJECTED` at the edge), not a 500.
- [x] `validate_where_clause("fl.is_fraud = 1")` raises
      `InvalidWhereClause`; `draft-rule` on such an insight → 400 and
      `SELECT count(*) FROM rules` for that insight is 0.
- [x] Pin with `sql: "THIS IS NOT SQL"` → 400 `SQL_REJECTED`.
- [x] Full backend suite green (`uv run pytest tests -q`).

P6b — each verified by the interactive session (LLM driving the browser,
snapshot after each step):

- [x] Refresh mid-conversation restores the conversation, its pinned
      insights, and the draft rule (none lost).
- [x] "New chat" keeps previous conversation's pins/rules reachable from the
      rail.
- [x] Rule drawer opens in draft, ready-to-backtest, deployed, and backtested
      states; re-clicking a rule always reopens it.
- [x] Editing the WHERE clause and saving issues `PATCH /v1/rules/{id}` and
      the clause updates in the UI.
- [x] A failed re-run marks the previous result stale and the error banner
      shows `error.message` (not "Error. Re-run failed.").
- [x] Chaos pass: the backend killed mid-stream does not wedge the UI — the
      send control re-enables, and state re-hydrates from the API after the
      backend is back.
- [x] All 15 findings from `../ux/fsm-evaluation-findings.md` are either
      fixed or explicitly re-scoped in that doc.

## Order

P6a first (P6b's error UI and clause editor assume the fixed contract), then
P6b. P6a is TDD with a test per task; P6b is built to the B1–B10 spec and
verified by the interactive session + chaos pass above — no automated
frontend test runner.
