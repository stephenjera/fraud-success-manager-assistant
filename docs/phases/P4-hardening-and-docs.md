# P4 — Hardening & docs

**Status:** in progress (2026-09-04).

The last phase. Ships `make eval` with zero red assertions and a README
that matches the code.

**DoD (verifiable):**

1. **`make lint` / `make test` / `make eval` all green.** `make lint`
   runs ruff + mypy. `make test` runs the pytest suite.
   `make eval` runs the deterministic eval subset (validator, flags,
   backtest math, rule state, rule engine, wall test). The eval harness
   is `backend/eval/harness.py` — a slim Python runner, not promptfoo
   (promptfoo is a global npm tool, not repo-local). These are
   *the* deliverables (spec §14) and are runnable by hand in the repo
   with no CI pipeline required (ADR-0012).
2. **README reconciled to actual state.** Names P0–P3 done, P4 in
   progress. Describes what's built (agent, core gates, rule lifecycle,
   frontend, eval suite). Points to `docs/system-spec.md` and
   `docs/decisions/`.
3. **ADR tree complete and consistent.** ADR-0001 through ADR-0016 all
   `accepted`. ADR-0016 formally rejects PostgresSaver (the deferral
   path from ADR-0013). All architecture docs updated to match
   (agent-loop.md, components.md, data-model.md, deploy.md).
4. **Wall test passes.** `tests/test_architecture.py` is a plain pytest,
   in the repo, passes in a fresh checkout with `uv sync`.
5. **Postgres story end-to-end.** Docker Compose at root spins up
   `postgres` (two roles, ADR-0007), `api` (alembic + seed + uvicorn),
   `frontend` (Vite → nginx), `pgadmin` (optional). No Langfuse in
   the stack (ADR-0010 / spec §12).

**What P4 explicitly does *not* do:** add features, add dependencies,
add a CI pipeline (out of scope until a real deployment target
exists — ADR-0012). Promptfoo LLM-evaluated suites (NL→SQL accuracy,
explanation faithfulness, safety/refusal) are documented in
`eval-design.md` but not wired — deferred until a judge model is
available.
