# Deployment & containerization

**Status:** accepted (frozen in the 2026-09-02 P0 freeze, same pass as the
other architecture docs).

ADRs 0001/0007/0008 fixed the stack (Postgres), the topology (one
cluster, two schemas, two roles), and the DDL owner (Alembic). This doc
answers the one question those left open: **what actually gets
started, in what order, and where the boundary sits** — containers,
ports, volumes, seed ordering, and the two things that are *not*
deployed (the LLM, the rule engine).

## What runs

| Service | What it is | Why it's here |
|---|---|---|
| `postgres` (compose) | `pgvector/pgvector:pg16`, one cluster, two roles inside (ADR-0007) | the only data store |
| `pgadmin` (compose) | dev-only browser for the cluster | optional, never load-bearing — the SQL is in Alembic + the seed |
| `api` (not a container) | the FastAPI app: `routers/` + `services/` + `agents/` + `core/` | runs from the local venv (see below) |

**The LLM is not a service.** Ollama is on-host (`LLM_API_BASE` in `.env`,
currently `http://localhost:11434`). Provider is config, not a component:
swapping to OpenAI/Anthropic is an env-var change (spec §2 scope), never a
deployment change.

**The rule engine client is not a service.** It's an in-process mock
(spec §9) that lives inside the `api` code. There is nothing to deploy;
the catalog of rules it would ship is exactly the `deployment_records`
rows the FSM writes. (See `context.md` for the "inside the boundary"
call.)

## Why the `api` is not a compose service

Local-first, deliberately. The loop is `uv sync` → `alembic upgrade
head` → `uv run uvicorn --reload`. A compose `api` service would buy
nothing at this stage (single local dev, no replicas, no network to
worry about) and cost a Dockerfile (ADR-0012: no Dockerfile until it
has a customer). The compose file's job is to bring *Postgres* up; the
API talks to it over the loopback port. If a real deployment target
ever shows up, the `api` service gets added then — the ADR-0012 skip
line is already recorded.

ADR-0012 already has the row that covers this (Terraform / real
deployment targets); this compose decision rides on the same one.

## Ports & volumes

| Port | Where | Why that number |
|---|---|---|
| `5433` host → `5432` container | compose `postgres` | host `5432` is already used by a separate local Postgres (the dev note in `backend/.env`); container stays canonical at `5432` |
| `5050` → `80` | compose `pgadmin` | dev-only; the number is not a decision |
| `11434` | Ollama, on-host | `LLM_API_BASE` in `backend/.env` |
| `8000` | `api`, local venv | `backend/README.md`'s `uvicorn --port 8000`; never a port in compose because the API is not a container |

Volumes:

- **`./database` → `/var/lib/postgresql/data`** (named local path).
  Survives `docker compose down`, wiped with `down -v`.
- **`./db-init` → `/docker-entrypoint-initdb.d`** (ADR-0015): the
  *bootstrap* path — role and schema DDL only (`001-roles.sql`,
  `002-schemas.sql`), idempotent. The ADR-0008 concern (init scripts
  silently no-op on a repeat init) is neutralised by idempotency;
  everything that grows across phases still moves through Alembic
  revisions, so the audit trail that motivated ADR-0008 is intact.

Everything else — env vars, `servers.json` for pgadmin — is passed
through, not mounted.

## Boot order (the only ordering that matters)

```
1. docker compose up -d postgres         # wait for healthy
                                          #    entrypoint runs db-init/001-roles.sql + 002-schemas.sql
                                          #    (idempotent — the fresh-volume bootstrap path, ADR-0015)
2. alembic upgrade head                  # appstate tables only, runs as app_rw (non-superuser)
                                          #    + checkpoints table (via the PostgresSaver.setup on first use)
3. python scripts/seed_reference.py      # TRUNCATE + COPY, idempotent, superuser (ADR-0008)
                                          #    + GRANT SELECT on all reference tables to reference_readonly
4. uv run python -m uvicorn app.main:app --reload --port 8000
```

Order is load-bearing: step 1 creates the `app_rw` role and the `reference` schema,
so step 2 (running as `app_rw`) can `CREATE` its own `appstate` tables.
Step 3 is the *first* place a superuser can write to `reference`, and it
also owns the `reference_readonly` SELECT grant (ADR-0015 moved it here —
it is an operation on a superuser-owned table, so it belongs in the
superuser's script, not in the non-superuser alembic migration).
Step 4's `app` connects as `app_rw` only — it does not, and cannot,
write to `reference` (the ADR-0007 floor, exercised daily by every
`run_sql` call). On an existing volume the order is `alembic upgrade
head` → `seed` → `uvicorn` — the entrypoint scripts do not re-run,
which is why they had to be idempotent to begin with. ADR-0015's
"wrong downgrade on an existing cluster is a boring `DROP TABLE`"
holds because `app_rw` has no right to drop the schema or the roles;
that is the floor that makes the boring path the *only* path.

## The Langfuse boundary

Langfuse is **not a container, not in this repo, not in any compose
file here.** It is *you-run, external* (spec §12, ADR-0012 skip row).
The app reads `LANGFUSE_BASE_URL` / `LANGFUSE_PUBLIC_KEY` /
`LANGFUSE_SECRET_KEY` from env; if they're unset, the entire tracing
path is a no-op (the app is fully demoable with Langfuse entirely
absent — that's the `GET /api/health/ready` "Langfuse configuration
state" line in `backend/README.md`). The boundary call — is it
*outside* the system? — is answered in `context.md`; this doc just
records the deploy consequence: **there is nothing to stand up, no
container to start, and no deploy step that cares whether it's
running.**

## Skipped (ADR-0012 record)

| Skipped | Why the line is here |
|---|---|
| CI pipeline | ADR-0012 skip row; no runner until there's a customer |
| Terraform / real deployment target | ADR-0008 consequences; the "repro on a fresh cloud host" capability has no user in this project |
| Multi-tenant postdeploy, WAF, rate-limit tiers | ADR-0012 skip row |
| A `Dockerfile` for `api` | ADR-0012 skip row; single-local dev has no customer for this today |

## Depends on

- ADR-0001 (Postgres, not SQLite)
- ADR-0007 (one cluster, two schemas, two roles)
- ADR-0008 (Alembic owns DDL; `scripts/seed_reference.py` owns data)
- ADR-0012 (the skip lines are its record, not this doc's)
- ADR-0015 (bootstrap DDL in `db-init/*.sql`; Alembic owns `appstate` tables only, non-superuser)

## Out of scope (see other docs)

- The *roles and permissions* inside Postgres → [data-model.md](data-model.md).
- The *agent loop* the `api` process runs → [agent-loop.md](agent-loop.md).
- What's *inside vs outside* the system boundary → [context.md](context.md).
- The *shape* of the eval suite's synthetic-pattern setup (it reuses the
  seed script's superuser pattern) → [eval-design.md](eval-design.md).
