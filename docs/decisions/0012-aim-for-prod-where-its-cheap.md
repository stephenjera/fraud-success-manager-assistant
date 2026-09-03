# ADR-0012 — Aim for prod where it's cheap; skip where it isn't

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

Recurring tension in this project: a "local prototype" that also wants to
demonstrate "how you'd actually build this." The tension has been
*resolved case by case* in this conversation, and each ad-hoc resolution
was being lost the moment the session closed. This ADR records the
*principle* so future cases are settled in one line instead of re-litigated.

## Decision

**Aim for prod standards where the cost is cheap and the gap is real.
Skip where the gap is a fake or the cost is a real project we don't have
customers for.**

The cost line is not "how hard is it to write" — it's "does skipping this
create a *knowledge gap* (a skill/pattern we'll need later and don't have
a working example of) or does it just save us a checkbox?" If it saves a
checkbox, skip it. If it saves us a knowledge gap, do it.

Concretely, the two sides of the line in this project:

| **Produce** (prod-grade, in scope) | **Skip** (out of scope, recorded as a boundary) |
|---|---|
| Versioned routes (`/v1/`) | CI pipeline |
| `DELETE` for all resource types | Terraform (ADR-0008) |
| Command/query SSE split (ADR-0011) | Multi-tenant isolation |
| Envelope + typed error shape | WAF, rate-limit tiers |
| ADR tree (`docs/decisions/`) | Real rule-engine client (spec §9) |
| `tests/test_architecture.py` wall check | Feedback loop / drift monitoring (spec §15) |

This is not a "we do everything" or "we do nothing" stance. It's a
*rule* for deciding the cases we haven't met yet, which matters because
this spec is live and the next phase will hit cases this list doesn't
cover.

## Consequences

- Every "should we do X?" question in P0–P3 gets a one-line answer:
  "does skipping X create a knowledge gap?" If yes → do it; if no →
  skip and record it in the skipped column of *this* ADR or a future one.
- The list is a *starting position*, not a law. New decisions that touch
  the production bar go here first, as a `Consequences` entry, before
  they become a code commitment.
- The ADR-0008 (no Terraform) and spec §15 (no feedback loop) positions
  are the same logic as "skip where the gap is a fake" and are covered
  by this ADR as the *principle*, not a separate decision.
