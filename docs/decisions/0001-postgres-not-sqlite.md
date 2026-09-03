# ADR-0001 — Postgres, not SQLite

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

Spec v2 was written for the challenge MVP and deliberately excluded Postgres
(§2: "no second environment this prototype runs in"). We've since re-anchored
on the spec as the *target system* we want to build, and chosen to work
against a real relational engine rather than SQLite's single-file limits —
notably that its read-only mode (`?mode=ro`) is a calling-convention, not a
permission, and its single-writer model doesn't suit concurrent backtests.

## Decision

Use **Postgres** for both the read-only reference dataset and the
application state. SQLite is retired from data access entirely.

## Alternatives considered

- **Keep SQLite** (original spec §2). Rejected: we are now targeting the
  full system, not the 4–5h MVP, and the "enforce read-only at the
  permission layer" claim (spec principle 2 / §11.1) is structurally
  impossible in SQLite — it's a mode, not a privilege.

## Consequences

- Spec §2's "Postgres out of scope" is **removed**; §6.4 "two SQLite files"
  becomes **two Postgres schemas** (see ADR-0007).
- The "never executes unsafe SQL, enforced at the permission layer" property
  becomes true by construction, via DB roles (ADR-0007).
- Adds one Postgres instance to the app compose stack; the agent's
  connection and the app's persistence use different roles (ADR-0007).
- Schema/role ownership moves to migrations (ADR-0008).
