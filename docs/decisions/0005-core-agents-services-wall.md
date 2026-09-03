# ADR-0005 — Three layers: core / agents / services, with a one-way wall

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

Spec principle 3 ("backtesting and evaluation are computation, not
conversation") and the rationale in ADR-0004 both depend on a guarantee that
no LLM-involved path can skip a deterministic safety step. A docstring alone
doesn't deliver that.

## Decision

Three layers with a load-bearing rule between them:

- **`core/`** — deterministic, LLM-free gates: `sql_validator` (ADR-0002),
  `flags`, `backtest` (metrics math), `rule_state` (state machine),
  `rule_engine` (the mock client). Pure functions or read-only-role SQL.
- **`agents/`** — LLM only. Reaches the database **exclusively** through its
  tools in `tools.py`, which call `core/`. It cannot open a connection.
- **`services/`** — orchestration: wires agent → core → data, and enforces
  ordering that must hold (e.g. a backtest row must exist before a rule
  becomes `backtested`).

The invariant: **`agents/` depends on `core/`; `core/` never depends on
`agents/`; the DB is reachable only via `core/` (reference, via the
read-only role) or `services/` (appstate).** The `agents → core` edge is
enforced by a `tests/test_architecture.py` AST check (assert `app/core/**`
contains no `from app.agents import`), so the wall is a running test, not a
comment.

## Alternatives considered

- **A single monolithic `service.py` for a prototype (ponytail cut).**
  Rejected explicitly: the split is exactly what ADR-0004 needs to make
  "the guarantee lives in code, not a prompt" true. Merging the layers would
  re-open the path the supervisor pattern is trying to close.
- **Four layers (separate `data/` layer).** Considered and folded into
  `services/` for a prototype; the repo still holds `data/` (engine,
  session, models, repos) as the persistence concern below all three — it is
  not a fourth *logical* layer, it's plumbing.

## Consequences

- Each package's `__init__.py` states its responsibility **and its
  prohibition** ("no import of `app.agents`, no network").
- The wall is machine-checked, so it survives refactors that would otherwise
  quietly leak a direct DB call into the agent or skip a validator.
- Depth is retained deliberately despite ponytail pressure to flatten — this
  is one of the explicit "never simplify away" cases because it is the
  primary GenAI-mitigation mechanic.
