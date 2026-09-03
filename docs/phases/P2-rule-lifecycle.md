# P2 — Rule lifecycle

**Status:** done (2026-09-03). All five DoD items are met and verified.

**Verify it** (from `backend/`, needs the seeded cluster; the two gatekeepers
are the reproducibility of the DoD):

```bash
alembic current                 # → 0002_p2_rules (head)
.venv/bin/python scripts/e2e_walktalk.py   # shape walkthrough, full FSM walk → WALK PASSED
.venv/bin/python -m pytest -q   # state machine + freeze line + backtest + deploy + wall → 94 passed
```

Takes the "pattern I see" the FSM found in P1 exploration and turns it
into a concrete, backtested, deployable SQL `WHERE` clause — the spec's
§7 object model (Conversation → Message → Insight → Rule →
BacktestResult → DeploymentRecord) and §7 state machine
(`draft → backtested → approved → deployed`, `rejected` terminal
branch from `backtested`).

**DoD (verifiable):**

1. **The orphaned `compute_backtest` in `db.py` is wired in** — no longer
   dead code. A pinned insight can have a rule drafted, backtested, and
   its `BacktestResult` persisted to `appstate.backtest_results`
   (ADR-0007 `app_rw` role).
2. **The state machine is enforced** in `core/rule_state.py` (ADR-0005):
   illegal transitions (e.g. `deploy` from `draft`) return 409/422, not a
   silent no-op — that's a pytest, in the repo (spec §10.2).
3. **`draft` is FSM-explicit.** A rule only reaches `draft` from a pinned
   insight (spec §7.2) — not from anywhere in the chat. The FSM can edit
   the `WHERE` clause directly (spec §7.1 "edit-and-own") and re-trigger
   the backtest without returning to the agent.
4. **The mock deployment is real.** `core/rule_engine.py` assembles the
   payload (spec §9) — rule identity, provenance, full latest
   `BacktestResult` — and returns a fake external ID. The mock is the
   concrete `RuleEngineClient`; the real one slots in later without
   touching calling code (spec §9).
5. **The Postgres roles hold:** `reference_readonly` cannot write to
   `reference` (enforced, not checked), `app_rw` writes to `appstate`.
   The "never executes unsafe SQL" property (spec §3) is the same floor
   P1 established, now exercised by the backtest path.

**P2 addendum (2026-09-03) — live-mode verification + bug it surfaced.**

The DoD above is fully met and verified. On top, a **live-mode pass** was
run and recorded:

- `scripts/e2e_walktalk.py --live` — full 22-step FSM walk against a **real
  Ollama model** (`qwen3.8:27b-128k`) and a **real** `reference` reader;
  self-evidencing (prints the model's token counts, tool calls, SQL, and
  prose) and hard-fails if the fake graph's canned prose is detected. Pass.
- `scripts/agent_repl.py` — same live path as a free terminal; a sequence of
  progressively harder questions (count, two-table join, three-table
  `GROUP BY`, day-of-week split with test-data anomaly) all produced correct
  SQL and grounded answers; the model correctly profiled columns before
  writing literals and **flagged** the day-of-week split as a possible
  labeling artifact rather than overselling it.

These do not *replace* the DoD — they are the proof the DoD's "no fakes in
production" items (5) and the "eval suite is P4" item do not mask a broken
live path. The `--live` gate and the REPL are documented in
`../architecture/e2e-walktalk.md` (P2 addition section).

**Bug surfaced by the live run (fixed):** `profile_column()` in
`app/agents/graph.py` had `nulls = total - non_null_count` — mis-labelled.
`cards.card_type` showed `nulls: 3437` against a fully populated column.
The model worked around it (the schema is in its system prompt) but it was
wrong. Fix: `nulls = int(cur.fetchone()[0])` on the `WHERE col IS NULL`
COUNT query. Verified post-fix: `cards.card_type` → `nulls: 0, distinct: 3`.

**What P2 explicitly does *not* do:** the `features/` frontend that
*shows* the rule lifecycle (P3), the wireframes that *specify* it
(P0/ux, not P2), or a real rule-engine client (out of scope forever —
spec §9).
