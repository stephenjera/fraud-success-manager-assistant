# ADR-0006 — Structured output as an explicit node, not a prompt hope

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

Spec §6.2: the assistant returns a structured contract
`{sql, explanation, assumptions, tables_and_joins, flags}`, "not raw prose,"
and the frontend renders those fields directly. If that shape "comes out" of
the model by prompting, the UI must still parse prose to find the fields —
which is exactly the silent-failure mode the spec is trying to remove.

## Decision

The structured output is an **explicit terminal node in the LangGraph
StateGraph** (ADR-0003) that produces the contract as a validated typed
object (`app/agents/output.py`), with `flags` **injected from `core/flags`,
not self-reported by the model**. The model writes `explanation` /
`assumptions` / `tables_and_joins`; the SQL and the flags are the facts a
run produced. Nothing in the response body is free-form prose the client has
to parse.

## Alternatives considered

- **Prompt the model to "always return this JSON."** Rejected: that is a
  hope. A hope is not a guarantee — and the frontend would be one malformed
  turn away from a crash. This is the specific thing §3 principle 1
  (the model never invents data, every claim is grounded) is trying to
  prevent.

## Consequences

- The SSE event set and the `POST /messages` response both become stable
  typed payloads (feeds ADR-0010 / the API contract).
- The `flags` field is provably deterministic — a red-team / sanity test
  can assert it against a known result set, independent of the model.
- Cost: an extra node and a schema to version. Accepted — it's the whole
  point of the contract.
