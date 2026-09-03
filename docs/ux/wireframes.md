# UX / wireframes

**Status:** accepted (frames drafted 2026-09-02 against the frozen
`architecture/api-contract.md`).

What does the FSM actually click, in what order, and what does the system
do in response — drawn at the sketch level (not the real UI). The
`frontend/src/App.tsx` is still a placeholder div; the real build
(React/Tailwind/shadcn, ADR-0009 `features/` + `components/ui/`) lands in
P3. These frames are the *target* that build has to hit, and the
coverage check at the bottom is the "can the API support this, or does
something need to change" test.

**Format: minimal HTML, not Excalidraw.** Decision made 2026-09-02. A
three-*pane* wireframe is spatial (left → center → right); the Excalidraw
MCP lays its structural types out as a containment hierarchy, which reads
backwards for a UI (verified: the `nested` type put the center pane in the
far left and the two side panes stacked in the far right). For speed of
creation the frames are plain HTML/CSS — one file, no build, opens in any
browser. That fits the goal (sketches for a coverage check) better than a
fancier diagram would have; it is *not* a statement about the final tech.

Frame → file (all in this folder):

- **`wireframes.html` §1** — the main view: chat (left), SQL/results
  workspace (center), insights rail (right). The single default layout.
- **`wireframes.html` §2** — the same view with the insights rail
  push-expanding into a metrics panel (spec §13: center narrows, not
  overlays). Two states, one flow.
- **`wireframes.html` §3** — the Rule Catalog page (separate from the main
  view per spec §13), with the `status` filter and a rule-detail drawer.
- **`wireframes.html` §4** — the workspace with an edited SQL query
  visible, the "re-run" affordance, and the revision bump. Spec §7.1's
  "the edited query becomes the new live query for that thread," in a
  frame, not a docstring.

Each frame's elements are tagged with the API element they read from
(`GET`) or drive (`POST` / `SSE`); the **coverage check** table is the
per-affordance mapping.

## Coverage check — does the API support the frames?

All four frames map onto the frozen contract. **11 of 12 affordances are
covered with no API change needed.** One seam needs a call:

- **Confirmed covered (no change):** conversation switch / new; chat
  stream + live activity (SSE `tool_call.*`, `message.delta`); composer →
  answer (`201 {run_id}` + `run.*`); run status chip (SSE terminals);
  live SQL + cards + results (message DTO `grounding`); pin insight
  (`POST …/insights`, Gap B); insight cards; catalog filter
  (`GET /v1/rules?status=`); catalog detail + lifecycle verbs
  (`approve`/`reject`/`deploy`); metrics panel (`BacktestResult.
  metrics/.coverage/.temporal_stability/.sample`); rerun + revision
  (`POST …/rerun` sync, Gap H).

- **Open — the rail's "Evaluate" semantics (see the flag in
  `wireframes.html`).** Frames 1–2 put an *Evaluate* button on a pinned
  **insight**, but the backtest is a **rule** verb
  (`POST /v1/rules/{id}/backtest`); an insight has no metrics until a
  rule draft exists. Two coherent shapes, both blocked by nothing in the
  contract:
  - **(a) Two-step, one button** — "Evaluate" fires `draft-rule` then
    `backtest`. Simple UX; a draft rule now silently exists behind a
    button that read as "just evaluate."
  - **(b) Explicit hand-off** *(recommended)* — the rail button is
    *Draft rule* (→ rule created); the rule then owns its own *Evaluate*
    (backtest) in the catalog/detail. Matches the state machine
    (insight → draft → backtested) exactly, no hidden writes.
  Either needs no API change — only the button label/handling differs.
  Recommend (b), because it keeps the ADR-0005 wall ("one trigger verb
  per edge," `rule-lifecycle.md`) visible in the UI instead of tucked
  inside a button. **This decision is recorded here, not yet frozen into
  the contract — it does not require an ADR, it is a UI-semantics call,
  but the choice must be locked before P3 builds Frame 2.**

## Depends on

- `../architecture/api-contract.md` (the `GET`/`POST`/`SSE` every frame
  is tagged with; the DTOs the center pane renders — Gap A `grounding`,
  Gap B pin, Gap C `BacktestResult`, Gap H rerun).
- ADR-0006 (structured output = what the workspace renders as cards, not
  prose).
- ADR-0009 (`features/{chat,workspace,insights,catalog}` + `components/ui/`
  = the directory map Frames 1–2 and 3 correspond to).
- `../architecture/rule-lifecycle.md` (the insight → draft → backtested →
  approved/deployed line the rail and catalog encode).
