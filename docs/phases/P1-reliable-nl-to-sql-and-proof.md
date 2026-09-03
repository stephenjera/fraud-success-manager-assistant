# P1 — Reliable NL→SQL + its proof

**Status:** done (2026-09-03). All six DoD items are met and verified. Scope
locked per ADR-0013: the **explore loop** — NL → grounded SQL → answer, proven
by tests. The rule lifecycle (pin → draft → backtest → approve → deploy) is P2.

**Verify it** (from `backend/`, needs the seeded cluster):

```bash
alembic current                 # → 0002_p2_rules (head)
.venv/bin/python scripts/e2e_walktalk.py   # shape walkthrough (Phases 1-3 here, 4-7 in P2) → WALK PASSED
.venv/bin/python -m pytest -q   # wall + validator + flags + explore loop + SSE → 94 passed
```

**Is the challenge deliverable.** By the time P1 is done, the FSM can
ask a question in natural language and get back an accurate, grounded,
structured SQL answer — and we can *prove* that with a suite of
tests in the repo.

**DoD (verifiable, not a mood):**

1. **Structured output is a real node** (ADR-0006) — not a prompt hope.
   The grounding payload `{sql, explanation, assumptions,
   tables_and_joins, flags}` is a typed object the API emits. The
   `flags` field is provably deterministic (assertable against a known
   result, independent of the model) — that's the ADR-0005 wall showing
   through.
2. **SSE streaming works** for the frozen event set (see
   `../architecture/api-contract.md`). The frontend (P3 builds its UI, but P1
   provides the events) can react to `run.start` / `tool_call.start` /
   `tool_call.done` / `message.delta` / `run.done` / `run.error` (with
   `insight.suggested` optional, and `run.timeout` as the third terminal) — in
   that order, exactly the names in the frozen contract.
3. **`tests/test_architecture.py` wall check passes** (ADR-0005) —
   `app/core/**` contains no `from app.agents import`. This test is in
   the repo on P1, not invented in P4.
4. **The endpoint and wall proof suite passes.** `tests/test_api.py` covers
   every P1 route (conversations, the explore loop, the runs/SSE view, `rerun`,
   `revisions`, the frozen error envelope); `tests/test_events.py` locks the
   SSE bus contract (fresh-subscriber and replay semantics); together with the
   existing wall + validator + flags tests, `pytest` is green. The eval
   harness (promptfoo + a judge model distinct from the agent) is P4.
   (`make eval` is a P4 member — see ADR-0013.)
5. **The E2E walkthrough of the explore loop runs green.**
   `backend/scripts/e2e_walktalk.py` walks **Phases 1-3** of
   `../architecture/e2e-walktalk.md` (session start, first grounded turn, edit
   + re-run) and asserts the *shape* of every response against the frozen
   `../architecture/api-contract.md`. Phases 4-7 (pin → draft → backtest →
   approve → deploy → catalog) are a P2 deliverable.
6. **The Postgres roles (ADR-0007) are live**: `reference_readonly`
   cannot write (try it), `app_rw` can write to `appstate` (try it).
   The "never executes unsafe SQL, enforced at the permission layer"
   property from spec §3 is no longer aspirational.

**What P1 explicitly does *not* do** (out of scope, in the spec still
open): the rule lifecycle and the Phases 4-7 walkthrough (P2), the
`features/` frontend (P3), hardening/docs and the eval harness (P4).
The PostgresSaver checkpointer is deferred to P2 (ADR-0013) — P1 runs the
in-memory checkpointer; the durable state is the `appstate` rows.
