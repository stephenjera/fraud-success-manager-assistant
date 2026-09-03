# ADR-0007 — One Postgres cluster, two schemas, two roles

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

ADR-0001 moved us to Postgres. Spec §6.4 had "two SQLite databases" as the
isolation mechanism. The honest read: there are two *kinds* of data here —
a **read-only reference dataset** (cards, transactions, …) and
**application state** (conversations, insights, rules, backtests,
deployments) — and the load-bearing property is that the agent can never
write to the reference data, while the app can freely write its own state.

## Decision

**One Postgres cluster**, two **schemas** (`reference`, `appstate`), two
**roles**:

| Role | Privileges |
|---|---|
| `reference_readonly` | `SELECT` only, on `reference.*` |
| `app_rw` | DML on `appstate.*` |

The **agent** connects as `reference_readonly` and cannot express an intent
to write. The **app** connects as `app_rw` for its state. This makes
spec §11.1 / principle 2 ("enforced at the permission layer, not just
prompted against") literally true — a `DROP`/`INSERT` is a *permission
denied*, not a caught exception.

## Alternatives considered

- **Two separate Postgres databases.** Considered; a harder boundary but buys
  nothing we use (we don't need cross-DB isolation or separate backup
  cadence). Two schemas in one cluster is the right altitude and keeps a
  single `DATABASE_URL` in the compose file.
- **One role with grants the app revokes at call time.** Rejected: relies on
  the app remembering to revoke. A dedicated role is the floor.

## Consequences

- The sqlglot validator (ADR-0002) is defense-in-depth; the **role is what
  actually stops the write**. The two reinforce each other.
- Schema/role DDL is owned by migrations (ADR-0008), not the compose
  container.
- Reconnects and pool config now target one `postgres://` URL.
