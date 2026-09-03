# P3 — Frontend — placeholder

**Status:** placeholder. Lands when P0 finishes; the wireframes in
`../ux/wireframes.md` are the acceptance, not the description.

Builds the three-pane + catalog UI the spec §13 describes, **against the
frozen API contract** (`../architecture/api-contract.md`) — that's the
contract-first rule: the frontend is the *consumer* of P0's freeze, not
a co-author of it.

**DoD (verifiable):**

1. **The four features exist** (ADR-0009) under
   `frontend/src/features/{chat,workspace,insights,catalog}/`. Each owns
   its area's API client, hooks, components, and local state — not
   smeared across a `components/` tree and a separate `hooks/` and an
   `api/`.
2. **`components/ui/` holds the primitives** (Button, Badge, Card, the
   shared results table, the stat-card) — reused across all four features.
   ADR-0009's rule of thumb is visible in the tree: "dumb" in
   `components/`, "does things" in `features/`.
3. **The SSE events from P1 are consumed**, not parsed from prose. The
   chat area reacts to `tool_call_start` / `tool_call_done` /
   `message_delta` / `done` / `error` (the frozen set) and shows
   "querying database…" inline — spec §6.5 in a frame, not a spinner.
4. **Every wireframe in `../ux/wireframes.md` is implemented** and the
   interaction matches. Specifically:
   - The three-pane default (left/center/right) renders.
   - "Evaluate" on a pinned insight **push-expands the rail into a
     metrics panel** (center narrows, not overlays) — the spec §13
     right-rail rule, in a clickable state.
   - The **Rule Catalog page** is reachable, filterable by status, and
     selecting a rule opens its detail **without reopening the
     originating conversation** (spec §13).
   - **Edit-and-own** (spec §7.1): the FSM edits a query in the
     workspace, re-runs it, and the edit is the new "live" query —
     visible in the UI, persisted where it should be (per the data-model
     decision, `../architecture/data-model.md`).
5. **The wall is honored** — the frontend never calls the agent directly
   for a safety-gated action. It goes through the `api/` (P2 endpoints),
   and the API goes through `core/` (ADR-0005). The frontend is the
   *consumer* of the contract, and only that.

**What P3 explicitly does *not* do:** auth, RBAC, real deployments,
multi-tenant isolation — all spec §15, explicitly deferred.
