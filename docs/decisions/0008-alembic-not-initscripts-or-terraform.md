# ADR-0008 — Alembic owns Postgres state (roles, app-state DDL), not init scripts / Terraform

**Status:** accepted (frozen in the 2026-09-02 P0 freeze); **superseded in part by ADR-0015** — the role/schema/GRANT DDL moved out of Alembic into `db-init/*.sql`, and the seed now owns the `reference` SELECT grant. The "Alembic owns the `appstate` tables, Terraform rejected, init scripts rejected as the *table* path" core survives.
**Date:** 2026-09-02

## Context

ADR-0007 introduced Postgres with two roles and an `appstate` schema that
will *grow across phases* (P1 adds conversations/messages; P2 adds
insights/rules/backtests; P3 adds the catalog views). Something must own
that DDL. The three candidates we considered are: **init scripts**
(`docker-entrypoint-initdb.d`, the current setup), **Terraform**, and a
**migration tool**.

## Decision

**Alembic** owns all structural DDL: the `reference` and `appstate` schemas,
the two roles and their GRANTs (ADR-0007), and the `appstate` tables. The
reference *data* (the 100 MB of cards/transactions/…) is loaded by a
separate `scripts/seed_reference.py` because data is not code — the seed is
idempotent (`TRUNCATE` + `COPY`, safe to re-run).

## Alternatives considered

- **`db/init/*.sql` init scripts** (current setup). Rejected: the Postgres
  entrypoint runs these *only on first volume init*. Change a schema,
  `docker compose up` again, and they silently no-op because the volume
  already exists. No revision history. A latent "my schema change didn't
  apply" failure with no audit trail.
- **Terraform.** Rejected: its payoff is "repro on a fresh cloud host
  against a real Postgres cluster" — a capability with no customer in this
  project. Spec §2's "no infrastructure-without-a-user" rationale applies
  harder here than to CI. If a real deployment target ever exists, add it
  then. This is a checkbox decision.
- **SQLAlchemy `create_all` + roles in `db/init`.** Rejected: fewer moving
  parts, but drops clean schema *changes* (which we need — `appstate` grows)
  and lands us back on the fragile init-script path for roles.

## Consequences

- `alembic upgrade head` is the single, orderable, reviewable path to the
  target schema and role state on any fresh or existing cluster.
- Role DDL lives in the same revision system as table DDL, so "the
  `reference_readonly` role exists" and "the `appstate.messages` table
  exists" are one atomic migration and one rollback — not two concerns in
  two places.
- Compose stops caring about schema contents; it just brings Postgres up.
  Schema creation is a backend concern.
- `scripts/seed_reference.py` is the *only* path that touches the
  `reference` schema's *data* — and it runs as a separate superuser, not as
  `reference_readonly` (which can't write anyway).
