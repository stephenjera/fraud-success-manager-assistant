# P4 — Hardening & docs — placeholder

**Status:** placeholder. The last phase, the one that ships
`make eval` with zero red assertions and a README that matches the code.

**DoD (verifiable):**

1. **`make lint` / `make test` / `make eval` all green.** `make lint`
   runs ruff + mypy (the toolchain is already pinned in
   `backend/pyproject.toml`). `make test` runs the pytest suite.
   `make eval` runs promptfoo + pytest and prints a summary. These are
   *the* deliverables (spec §14) and they are runnable by hand, in the
   repo, with no CI pipeline required (CI is explicitly out of scope per
   ADR-0008 — the make targets *are* the CI-ready equivalents).
2. **README is reconciled to the actual state.** The root `README.md`
   currently says "V5 baseline, agents/skeleton exist, feature work not
   started." By P4, that is false, and the README says what's actually
   built: the agent, the core gates, the rule lifecycle, the eval suite,
   the frontend. It points to `docs/system-spec.md` (the authoritative
   spec, moved from the repo root per ADR-0010) and to
   `docs/decisions/` (the "why" for every load-bearing choice).
3. **The ADR tree is complete and consistent.** All ADRs are
   `accepted` (P0's freeze). No ADR is in a `proposed` state past P0.
   The cross-references (e.g. ADR-0001 → ADR-0007, ADR-0004 → ADR-0005)
   resolve and the "Superseded by" path is ready for any future
   revision — the mechanism exists even if no ADR is superseded, which
   is the *good* outcome.
4. **The wall test passes in CI-ready shape.** `tests/test_architecture.py`
   (ADR-0005) is a plain pytest, in the repo, and will pass in a fresh
   checkout with `uv sync` + `alembic upgrade head`. That's the whole
   "make targets are CI-ready" claim, in one file.
5. **The Postgres story is end-to-end.** From a clean `docker compose
   up`, the operator has: one `postgres` (two roles, ADR-0007), the
   `api` running against the `app_rw` role for state and the
   `reference_readonly` role for data, the `seed_reference.py` script
   (ADR-0008) loaded, `pgadmin` available but optional. No Langfuse in
   the stack (ADR-0010 / spec §12) — the `api` no-ops if the
   `LANGFUSE_*` env vars are absent.

**What P4 explicitly does *not* do:** add features, add dependencies,
add a CI pipeline (out of scope forever until a real deployment target
exists — ADR-0008).
