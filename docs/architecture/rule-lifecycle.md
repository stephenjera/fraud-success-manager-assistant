# Rule lifecycle & state machine

**Status:** accepted (frozen with the 2026-09-02 P0 freeze, same pass as `api-contract.md`).

What are the rule statuses, which transitions are legal, and **who triggers each one** (the FSM, a deterministic gate, or the agent)? This doc answers that and closes one gap the frozen contract left open: what `PATCH /v1/rules/{id}` does to a rule that already has a backtest.

The state machine itself is specified in spec §7; this doc makes each edge concrete — its trigger, its actor, where it is enforced, and the exact status change — so it can be implemented in `core/rule_state.py` and asserted in a test without a second design pass.

## The states

Five, not six:

| Status | Meaning | How you get here | How you leave |
|---|---|---|---|
| `draft` | A `WHERE` clause exists, no evidence yet, no decision. | `POST /v1/insights/{id}/draft-rule` (the only way a rule is created). | `backtest` → `backtested`. |
| `backtested` | Exactly one backtest row exists against this rule's **current** `WHERE`, the FSM has not decided. The `WHERE` is now sealed (see "The freeze line" below). | `POST /v1/rules/{id}/backtest` succeeds. | `approve` → `approved`; `reject` → `rejected` (terminal). |
| `approved` | The FSM has judged the evidence and chosen to ship it. `approved_by` / `approved_at` / `rationale` recorded. | `POST /v1/rules/{id}/approve` with `{rationale, actor}`. | `deploy` → `deployed`. |
| `deployed` | The deployment payload was assembled and sent to the (mocked) rule engine; a fake `external_rule_id` exists in `deployment_records`. | `POST /v1/rules/{id}/deploy`. | (terminal; see `disabled`). |
| `rejected` | The FSM judged the evidence insufficient and chose against it. | `POST /v1/rules/{id}/reject` with `{rationale, actor}`. | (terminal — there is no edge out). |

`disabled` is **not** a status. It is a flag on a deployed rule — a `disabled_at` timestamp set by `POST /v1/rules/{id}/disable`. A disabled rule still has `status: "deployed"`; the flag says "we stopped using this one, here's when." Keeping it out of the status set keeps the state machine at exactly the five states spec §7 defines and keeps `GET /v1/rules?status=…` honest (a disabled-and-deployed rule still appears under `deployed`).

## Edges and who fires them

Every edge is triggered by exactly one FSM `POST` verb. There are no self-transitions except re-backtest under a new time window. The agent is never the trigger of any edge — that is the ADR-0005 wall made concrete, and the `agents → core` AST check is the running test that keeps it true.

| From | To | Trigger | Actor | Where enforced | Notes |
|---|---|---|---|---|---|
| `draft` | `backtested` | `POST /v1/rules/{id}/backtest` succeeds — a row lands in `backtest_results` against the current `WHERE`. | FSM | `core/rule_state.py` gate over the row insert; `core/backtest.py` does the math. | The gate *is* "a row exists." No row, no transition. |
| `draft` | `draft` | `POST /v1/rules/{id}/backtest` fails (409 — no row, or the `WHERE` fails validation). | FSM | same gate. | Stays in `draft`; no row is a valid "I tried and it didn't pass" state. |
| `backtested` | `approved` | `POST /v1/rules/{id}/approve` body `{rationale, actor}`. | FSM | `core/rule_state.py`. | Recorded with `approved_by`, `approved_at`, `rationale`. |
| `backtested` | `rejected` | `POST /v1/rules/{id}/reject` body `{rationale, actor}`. | FSM | `core/rule_state.py`. | Terminal. No `rejected → draft` edge. |
| `approved` | `deployed` | `POST /v1/rules/{id}/deploy` → mock `core/rule_engine.deploy_rule` returns a fake `external_rule_id`; a row lands in `deployment_records`. | FSM | `core/rule_state.py` gate *plus* the successful mock call. | The mock is the only path to an external ID (spec §9). No mock success, no `deployed`. |
| `backtested` | `backtested` | `POST /v1/rules/{id}/backtest` again (same `WHERE`, new `window`). | FSM | same gate as `draft → backtested`. | Self-loop. New `backtest_results` row; status unchanged. The "tune the time slice, not the logic" path. |
| any | any | `PATCH /v1/rules/{id}` — `title` only. | FSM | no gate. | Cosmetic. Allowed in every status; a title is not evidence and changing it does not invalidate a backtest. |

Every edge in the table has exactly one trigger verb, and the trigger is always an FSM `POST`. The agent reaches none of them: `agents/` has no dependency path to `core/rule_state.py` or `core/rule_engine.py`, and the `agents → core` edge is the only way to the DB anyway (ADR-0005). That invariant is what the `tests/test_architecture.py` AST check asserts, and the per-edge tests in `tests/` (spec §10.2) assert each individual `409` on the illegal ones.

## The freeze line (and why it is what it is)

`PATCH /v1/rules/{id}` accepts `where_clause` in *any* status at the API level — that is the edit-and-own pattern, and it is correct for a rule that has never been backtested. But the moment a backtest row exists against the current `WHERE`, the `WHERE` and the backtest that justifies it form a **matched pair**: the precision/recall/FPR numbers in `backtest_results` are the evidence *of that specific `WHERE`*. Changing the `WHERE` after the fact, while keeping the backtest that was run against the old `WHERE`, is the hole — the deployment payload (spec §9) says "the receiving system gets evidence the rule was validated." Validation of a different `WHERE` is not that evidence.

The decision (2026-09-02, frozen): **the rule's `WHERE` is sealed once a backtest row exists against it.** Concretely:

- `POST /v1/rules/{id}/backtest` succeeds → the current `WHERE` is frozen. Any further `PATCH /v1/rules/{id}` body that includes a `where_clause` field returns **`409 RULE_ILLEGAL_TRANSITION`**. The `title` field in the same body is still allowed (it does not invalidate the backtest).
- A failed backtest (409 / validation failure, no row written) does **not** freeze the `WHERE`. `PATCH {where_clause}` on a `draft` rule always succeeds with `200` — that is the normal tune-the-clause flow before you commit to an evaluation.
- **`rejected` is terminal; there is no `rejected → draft`.** If the FSM wants to try again with a different `WHERE`, the path is `POST /v1/insights/{id}/draft-rule` again — a **new rule**, a new `rule_id`, a fresh `draft` state. The old rejected rule and its rationale stay in the catalog as the record of "we tried this and said no." This is a sibling object, not a transition, and it is the spec's exact phrasing (§7: "rejected as a terminal branch from backtested" — not "a branch that can come back").
- The deployment payload, `GET /v1/rules/{id}` detail, and `BacktestResult.sample` all reference the same `WHERE`: the one that was live when the latest backtest row was written. Because the freeze line makes that pair matched, the payload never silently drifts from the evidence.

Why sealed-and-sibling, not "roll back to draft on edit" (the 200 alternative): rolling back would let a `PATCH` on an `approved`/`deployed` rule silently demote it to `draft` while its `deployment_record` still points at the old `WHERE` — the catalog would then have three inconsistent statements (deployment row, rule status, backtest row) about what is actually live. Sealing the `WHERE` at backtest time means the `PATCH` returns `409` and the FSM is forced to take the clean path (new rule from the same insight), which keeps the catalog unambiguous. That is the "one source of truth per object" property the ADR-0011 consequence for `rule.status` exists to protect — it just applies to the `WHERE` as well.

## The invariant, stated in one sentence

**Every `backtest_results` row and every `deployment_records` row is anchored to a specific `WHERE` that was live when the row was written; the state machine enforces that the `WHERE` cannot change while those rows exist, and that the only way to validate a different `WHERE` is a new rule from the same insight.**

That single sentence is the contract between `core/rule_state.py` (enforcement), `core/backtest.py` (row creation), `core/rule_engine.py` (deployment payload), and the four `POST` / `PATCH` verbs in the frozen API contract. Any one of them changing the `WHERE` after a backtest row exists must return `409 RULE_ILLEGAL_TRANSITION`; the others must not.

## Dependencies

- ADR-0005 (the `agents → core` wall is the enforcement of the invariant; the AST check is the running test).
- ADR-0006 (structured output is the shape that `draft-rule` returns; the rationale/assumptions in the `draft` state come from there).
- ADR-0011 consequence (the `rule.status` field and `PATCH`/lifecycle-verb sharing a single source of truth is exactly what the freeze line extends to `where_clause`).
- ADR-0012 (the DELETE cascade in spec §7 is the "prod-standard" cost this doc accepts for a prototype).
- spec §7 (the state machine itself), §7.1 (edit-and-own), §7.4 (backtest never LLM-invoked), §8 (the BacktestResult DTO), §9 (the rule engine contract and deployment payload).
