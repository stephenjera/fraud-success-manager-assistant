# ADR-0010 — Decisions before diagrams; nothing is final until the P0 freeze

**Status:** accepted (frozen in the 2026-09-02 P0 freeze)
**Date:** 2026-09-02

## Context

The risk this project is trying to avoid — and the one you named directly —
is that decisions were made in conversation and then lost, leaving us to
*discover* the architecture instead of *choosing* it. The docs structure
exists to prevent exactly that.

## Decision

Two coupled rules, both recorded here because they shape every other
artifact:

1. **Decisions before diagrams. A diagram is the rendered output of a
   decision, never the input that produces thinking.** The flow is always:
   discuss a question → lock the decision (an ADR where it's a choice) → the
   diagram or doc expresses it. A file in `diagrams/` maps 1:1 to an
   `architecture/` doc, and that doc either answers a settled question or is
   a working placeholder.
2. **Everything in `docs/` is `proposed` until the end of Phase 0.** A
   `proposed` ADR may be revised or superseded whenever new information
   arrives. `Superseded-by` is a *normal* end state, not a failure. The
   cheap thing is changing a 30-line doc now; the expensive thing is a
   baked-in wrong decision in Phase 3.

## Consequences

- The ADR set in `decisions/` is **the record of our decisions**, not a
  future chore. Every entry records an actual choice with its
  alternatives, which is the content that would otherwise vanish when the
  session closes. As of this record the set runs ADR-0001 through
  ADR-0012.
- No diagram is "just a diagram." If we're about to draw one and can't
  point at the ADR that justifies it, we've got a question we haven't
  actually answered.
- The freeze happens once, at end of P0, and turns `proposed` → `accepted`
  en masse. After that, a change requires a new ADR + `Superseded-by` on
  the old one — the same mechanism, but now it's a *deliberate* revision
  instead of a drift correction.
- This ADR is deliberately the *last* in the set, written after the
  decision it records, and explicitly names the other ADRs it is about. If
  that smells circular, it is — the circularity is the point: the policy is
  what justifies the shape of the policy itself.
