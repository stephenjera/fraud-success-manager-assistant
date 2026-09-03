# ADR-0015 — Infrastructure as idempotent SQL init (roles, schemas, grants); Alembic owns appstate tables only

**Status:** accepted (supersedes the role/schema/grant clause of ADR-0008, 2026-09-03)
**Date:** 2026-09-03

## Context

ADR-0008 put *everything* through one tool: Alembic owns the two roles, the two
schemas, the GRANTs, and the `appstate` tables; `seed_reference.py` owns the
`reference` data. It rejected `db/init/*.sql` on the grounds that the entrypoint
"runs only on first volume init and silently no-op afterwards, with no revision
history."

That rationale is correct for *evolving table DDL* — and we keep Alembic for
exactly that. It is the wrong tool for the *static infrastructure* layer (roles,
schemas, grants), because those two categories have different lifetimes:

- roles / schemas / grants **change at deployment** — a schema re-shape, a new
  role — and are not in `alembic_version` history. Putting them in a migration
  means the only path to change them is a *new revision*, and a *wrong
  `downgrade` can do destructive things to a data schema. That is exactly the
  failure that occurred while validating this ADR: 0001's downgrade ran
  `ALTER SCHEMA reference RENAME TO reference_p1_removal` and stripped
  `reference_readonly`'s GRANTs, because `downgrade` could reach the data
  schema at all.
- the single-user local stack's reset model is `docker compose down -v` →
  re-init from source. On that path an idempotent SQL file is *more*
  trustworthy than a migration: there is no state to reconcile, and
  re-application is the repair path, not a bug.

## Decision

**Split Postgres state by lifetime, not by tool:**

- **`db-init/001-roles.sql`, `002-schemas.sql`** — idempotent SQL, the
  infrastructure layer (two `CREATE ROLE`s, `CREATE SCHEMA ×2`, the
  `appstate` ownership binding, the `app_rw` privilege on appstate). Runs via
  `docker-entrypoint-initdb.d` on a fresh volume, and re-applied with
  `psql -f db-init/*.sql` as the *repair path* against an existing cluster.
  Both files are safe to run N times (CREATE ... IF NOT EXISTS / idempotent
  role upsert).
- **`scripts/seed_reference.py`** — unchanged in scope, now explicitly the
  owner of the `reference` schema *and* its GRANTs (it creates the tables, so
  granting on them is its job): the SELECT grant to `reference_readonly` moved
  into the seed, alongside `CREATE SCHEMA IF NOT EXISTS reference`. The seed
  still runs as superuser and still owns the data.
- **Alembic** — owns *appstate tables only*. Runs as the non-superuser
  `app_rw` role (which owns the `appstate` schema via 002-schemas.sql, so it
  can CREATE/DROP `appstate.*` without ever touching `reference`, the roles,
  or the schema objects). `alembic_version` lives in `appstate`. A wrong
  `downgrade` is now a plain `DROP TABLE IF EXISTS appstate.<t>`: `app_rw`
  cannot drop the `appstate` schema, cannot drop the roles, and cannot read
  `reference`, so a mistyped rollback is boring and reversible (re-run `head`).

## Superseded

- **ADR-0008 "Alembic owns the two roles, the two schemas, and the GRANTs."**
  Those three move to `db-init/*.sql` + the seed. The rest of ADR-0008 stands:
  Alembic owns the *table* DDL (now only `appstate`), and `seed_reference.py`
  owns the `reference` data. ADR-0008's "Terraform / init scripts rejected"
  rationale is *overruled for the infrastructure layer only*: it applies to
  evolving DDL, which we keep in Alembic.

## Alternatives considered

- **Terraform / cloud IaC** — no customer in this project (ADR-0008, ADR-0012).
  The payoff ("repro on a fresh cloud host against a real cluster") is unused.
  If a real deployment target ever shows up, re-evaluate then.
- **SQLAlchemy models + `op.create_table`** — would require an ORM layer the
  runtime does not use (raw `psycopg`, zero `Base.metadata`), added purely so
  Alembic could autogenerate-diff against it. That is more code to maintain for
  tooling we do not otherwise use. The raw-SQL `op.execute` in `backend/` is
  deliberate: the codebase's spine is psycopg; the DDL is a one-time artifact
  per phase, not a continuously-iterated model surface.

## Consequences

- `db-init/*.sql` is the "infrastructure ready" line; `seed_reference.py` is
  the "data ready" line; `alembic upgrade head` is the "appstate tables ready"
  line. Each is idempotent in its own layer; the layers do not overlap.
- Boot order becomes: `docker compose up -d postgres` (init SQL runs) →
  `alembic upgrade head` (as `app_rw`) → `python scripts/seed_reference.py`
  (as superuser) → `uvicorn app.main:app`. The first two are reversible and
  order-independent for a fresh volume; the seed must follow alembic because
  it reads `appstate` is not required — it only writes `reference` — so the
  only real ordering constraint is that the `reference_readonly` role exists
  (step 1) before the seed grants (step 4).
- The fresh-cluster proof (`p2_fresh_proof.py` / the p2own run) is the
  regression: build all eight `appstate` tables on a clean DB via the three
  layers in order, and confirm each table is `app_rw`-owned and that
  `reference_readonly` can read `reference.transactions` but not write it.
- The "wipe the volume → re-init" model is now the *designed* reset path, not
  an escape hatch: the init SQL + seed + alembic reproduce the base state
  deterministically from source.
- `db/init/` (root-owned, empty, never wired) is a dead artifact from the
  pre-refactor attempt; the live mount is `backend/db-init/`. Delete
  `db/init/` when `sudo rm -rf` is available.
