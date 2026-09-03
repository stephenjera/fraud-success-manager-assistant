# ADR-0002 — sqlglot (parse) over regex

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

The agent can propose arbitrary SQL; it must never run DDL/DML against the
reference schema. The current guard (`backend/app/db.py:57`, `_validate_select`)
regex-scans a cleaned string for a set of forbidden keywords after a
single-`SELECT` check.

## Decision

Validate with **sqlglot**: parse to an AST and accept only a single
read-only `SELECT` (or, for rule drafts, a valid boolean `WHERE`
expression) over allow-listed tables/columns, in the **Postgres** dialect.

## Alternatives considered

- **Keep the regex** guard. Rejected on a real defect: a string *literal*
  containing a forbidden word — e.g. `WHERE merchant LIKE '%DELETE%'` or a
  value that contains `PRAGMA` — is rejected even though it is a harmless
  read. Conversely, obfuscated constructs a parser would flag are not
  reliably caught by keyword matching. The regex is both a false-positive
  source and weaker than it looks.
- **Keyword-list expansion.** Rejected: more branches to maintain, same class
  of problems, no dialect awareness now that the target is Postgres.

## Consequences

- sqlglot becomes a runtime dependency.
- Validation is dialect-aware (Postgres) rather than engine-agnostic
  keyword-scraping, so it stays correct across the ADR-0001 engine swap.
- Allow-listing of tables/columns is enforced structurally (the AST names
  them), not by string search.
