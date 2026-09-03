# docs/

The home of everything we've *decided* and *designed* — and, as importantly,
how we keep it from rotting.

## Reading order

1. `decisions/` — the ADRs. **Read these first.** They are the load-bearing
   choices and the "why." Start at `0001`.
2. `system-spec.md` — the authoritative spec (moving here from the repo root;
   the Postgres/sqlglot/LangGraph rewrites land in the same pass).
3. `architecture/` — one doc per design question (components, agent loop,
   rule lifecycle, data model, API contract, deploy, eval).
4. `phases/` — the roadmap and per-phase acceptance criteria.
5. `ux/` + `diagrams/` — the FSM's actual clicks, rendered.

## How a decision is recorded

One ADR file per decision — numbered, `NNNN-kebab-title.md`, with four
sections: **Context** (why now), **Decision** (the pick), **Alternatives
considered** (what we rejected and why — this is the part that would
otherwise be lost), **Consequences** (what it enables / forces).

### Status lifecycle

```
proposed  ->  accepted  ->  superseded
```

- **proposed** — agreed in a design session, not yet frozen. Every ADR in
  this repo is `proposed` until the end of Phase 0.
- **accepted** — frozen at the end of P0.
- **superseded** — replaced by a later ADR; the file stays, gains
  `Status: superseded by ADR-00NN`, and is kept for the trail.

**Nothing is final until the P0 freeze.** A `proposed` ADR may be revised or
superseded whenever new information arrives. That is the *purpose* of the
format, not a smell — the cheap thing is changing a 30-line doc now, the
expensive thing is discovering a baked-in wrong decision in Phase 3.

## How a diagram is earned

A diagram is the rendered **output** of a decision, never the input that
produces thinking. The flow is always: *discuss a question → lock the
decision (ADR) → the diagram expresses it.*

Rules:

- Every file in `diagrams/` maps **1:1** to an `architecture/` doc that asked
  a question. No doc, no diagram.
- `.excalidraw` is the source; we commit the **`.svg` export** too so a
  diagram change shows as a reviewable diff in a PR rather than "trust me,
  open the file."
- A diagram is redrawn when its decision changes (or superseded), not
  patched ad hoc.

## Folder map

| Path | What belongs here |
|---|---|
| `system-spec.md` | The single authoritative spec. Source of truth. |
| `decisions/` | ADRs. One decision per file. Never delete; supersede when superseded. |
| `architecture/` | One doc per design question. The "what/why" prose. |
| `phases/` | `00-roadmap.md` + `P0-architecture.md` … + per-phase DoD. |
| `ux/` | Wireframe notes + the interactions they encode. |
| `diagrams/` | Excalidraw sources + SVG exports, one per architecture doc. |

## State (as of the 2026-09-02 P0 freeze)

P0's freeze landed: **all ADRs `accepted`**, `system-spec.md` rewritten as
one coherent pass (the root spec removed), and every `architecture/*.md`
doc — including `api-contract.md` (frozen: routes/DTOs/SSE set/error codes
+ the four gap closures A/B/C/H) — has content. The UX frames are in
`ux/wireframes.html` (HTML, not Excalidraw — see the note in `ux/
wireframes.md` for why). The one still-open call is the rail's **"Evaluate"
semantics** (frames 1–2 in `ux/wireframes.md`), a decision to lock before
P3 builds the rail.

What's *not* done is the code, not the design: P1 (reliable NL→SQL + the
proof), P2 (rule lifecycle), P3 (frontend), P4 (hardening) are ahead in
`phases/00-roadmap.md`.
