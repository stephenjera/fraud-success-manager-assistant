# P0 — Reckon & lock — placeholder

**Status:** placeholder. Content lands when the phase's actual work
begins; this file exists only so the `phases/` folder is complete and the
cross-references from `00-roadmap.md` resolve.

P0's *deliverables* (the DoD from `00-roadmap.md` above, restated):

1. `docs/decisions/*.md` all flipped from `proposed` → `accepted`.
   Nothing else changes at this step — an ADR that's `accepted` is the
   freeze, and a freeze is a one-line status edit, not a rewrite.
   (The set is now ADR-0001 through ADR-0012; ADR-0011 and ADR-0012
   land in the P0 freeze with this pass.)
2. `docs/system-spec.md` is the one-coherent-pass rewrite of the root
   spec, driven by ADRs 0001–0012 (the re-anchoring ones). The root
   `fraud-insight-copilot-spec.md` is **removed** (the spec lives only in
   `docs/system-spec.md`, not mirrored).
 3. `docs/architecture/*.md` — the one-question docs have content. The
    **API contract** is the one we've already discussed and drafted
    (`api-contract.md`); P0's remaining job there is the freeze pass
    (naming the event names and error codes, confirming with a single
    edit each). The others (`context`, `components`, `agent-loop`,
    `rule-lifecycle`, `data-model`, `deploy`, `eval-design`) follow from
    ADRs mostly already written.
4. `docs/diagrams/*.excalidraw` (and their `.svg` exports, per ADR-0010)
   exist one-per-`architecture/*`-doc. The SVGs are what make the
   diagram changes reviewable.
5. The ADR-0005 wall test (`tests/test_architecture.py`) is written and
   passes — the wall is checked, not just described.

**What P0 does *not* do:**

- No feature code. No new dependencies beyond what the ADRs name.
- No implementation of the eval suite (that's P1).
- No frontend past the existing placeholder (that's P3).

**What P0 does *do*:**

- A `docs/system-spec.md` that a new contributor can read top-to-bottom
  and come out with the same mental model as the person who authored the
  ADRs.
- A `docs/phases/` tree where every subsequent phase has a *pointed-to*
  set of stubs that now have content.
- A diagram for every architecture doc where the doc has a clear
  question and a clear answer. No diagram for a question that's still
  an open question.
