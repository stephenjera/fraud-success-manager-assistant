# P6b — Frontend rebuild (implementation plan)

**Status:** planned, part of P6 (ADR-0017). Deps: P6a (done).
**Parent:** `P6-error-contract-and-frontend-redesign.md`
**Scope:** B1–B10 in the parent doc; fixes findings #1, #2, #5, #6, #7, #8,
#9, #10, #12, #14, #15 in `../ux/fsm-evaluation-findings.md`.
Findings #3, #4, #11, #13 are P6a. Finding #5's "Unnamed rule" half is
backend (`rules.title` seeded from the model's proposal in P5) — here we
make sure the UI doesn't fall back to an anonymous string.

One pass, task-by-task; `npm run build` (tsc) + `npm run lint` must be
clean after every task. No new dependencies, no new test tooling. After
the build: the interactive session + chaos pass from the parent doc's
**Order** and **P6b — DoD**.

## Reference specs (read these first)

- `P6-error-contract-and-frontend-redesign.md` — scope B1–B10, DoD.
- `../ux/fsm-evaluation-findings.md` — the 15 findings, verified live.
- `../ux/wireframes.md` — the target three-pane IA (`wireframes.html`
  frames 1–4 + the coverage check).
- `../architecture/api-contract.md` — the frozen wire.
- `../architecture/rule-lifecycle.md` §freeze line — why `PATCH
  /v1/rules/{id}` is the clause editor and why `where_clause` is only
  editable while `status='draft'` and no backtest row exists.
- `P6a-backend-fixes-implementation.md` — the error contract this UI
  consumes.

## Architecture / tech stack

React 19 + Vite + Tailwind v4 + shadcn/ui, all existing. The existing
`features/{chat,workspace,insights,catalog}` + `lib/{http,types,utils}`
are the only code we touch. `App.tsx` is the shell. `components/ui/`
is the primitive set.

Target layout (B2): three top-level panes, no view switch.

```
+---------------------------------+---------------------------------+---------------------------------+
| Conversations rail               | Conversation panel               | Rule workspace                |
| (list of conversations,          | (chat + pinned insights for      | (rule list + detail:        |
|  "New chat" button,              |  the active conversation, plus   |  title, status, clause       |
|  selected one highlighted)       |  the workspace for the selected  |  editor, rationale,          |
|                                  |  grounded turn)                  |  assumptions, backtest       |
|                                  |                                  |  detail, lifecycle verbs)    |
+---------------------------------+---------------------------------+---------------------------------+
```

The existing "Workbench / Rules Catalog" view switch goes away. The
catalog becomes the rule workspace. The insights rail is demoted to a
section inside the conversation panel (its "Draft rule" and "Evaluate"
verbs move into the rule workspace; its expanded metrics panel also
moves). The chat pane stays the chat pane.

## Global constraints

- **One task per B-item cluster.** Each task leaves the app in a working
  state: `npm run dev` renders, the existing flows still run, no dead
  button.
- **`npm run build` + `npm run lint` clean after every task.** That is
  the gate; there is no automated test runner to run instead.
- **No new dependencies.** `package.json` unchanged.
- **No `git add` of `docs/ux/`.** That tree stays untracked.
- **Commit per task**, message `feat(frontend): <what>`, with the
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
  trailer.
- **Preserve `components/ui/`.** Every existing shadcn primitive stays;
  we only add or remove feature- and shell-level files.
- **The wire contract is frozen** (`../architecture/api-contract.md`):
  we call the endpoints as documented, we do not add a backend endpoint
  or change the error envelope (that is P6a's job).

## Verified current behavior (baseline, do not re-derive)

**Code layout** (`frontend/src`):

- `App.tsx` — top bar with a `workbench | catalog` view switch; the
  workbench view is `ChatPane | WorkspacePane | InsightsRail`, the
  catalog view is `CatalogPane`.
- `lib/http.ts:5` — `API_BASE = import.meta.env.VITE_API_BASE ??
  "http://127.0.0.1:8000/v1"`. No `/api` proxy prefix; it is a
  cross-origin URL. `VITE_API_BASE` is not set in the tree.
- `features/chat/useChat.ts` — owns `conversationId`, `turns`, `busy`;
  has `newConversation` and `selectConversation` but neither is
  reachable from the UI (no conversation rail exists). `newConversation`
  clears all local state (turns, conversationId, error) but does NOT
  delete the conversation on the backend (confirmed: `useChat.ts:142–148`
  only touches local state).
- `features/insights/rail.tsx` — lists the pinned insights for
  `conversationId`; "Draft rule" (creates a draft via
  `rulesApi.draftRule`) and "Evaluate" (runs a backtest via
  `rulesApi.backtest`) are on each card; the rail push-expands into a
  `MetricsPanel` that shows the backtest's two-universe metrics +
  temporal stability + sample rows.
- `features/catalog/CatalogPane.tsx` — the rules list + a
  `RuleDrawer` for detail. **Bug 1 (finding #1):** `useChat`/rail
  state — the drawer has an `open` + `showDetail` pair; the close
  handler sets `showDetail=false` but never resets `open`, so a re-click
  on the same rule is a no-op. **Bug 2 (finding #14):** after `Backtest`
  succeeds, the card's `onChanged` sets `showDetail=false` and
  re-loads the list; the detail state is gone, the re-click on the same
  card hits the same `open`/`showDetail` bug. `CatalogPane.tsx:231–241`
  for the render condition, `CatalogPane.tsx:213–229` for the effect.
- `features/catalog/api.ts:56–57` — `draftRule` exists but `patchRule`
  does not (grep-verified). `PATCH /v1/rules/{id}` is documented in
  `../architecture/api-contract.md:255` but the UI has no editor.
- `features/workspace/WorkspacePane.tsx:63` — the error copy on a
  failed rerun is `e code — e message`, but when the 500 is CORS-blocked
  (pre-P6a), `e` is a network TypeError and the copy is just "Re-run
  failed."
- The `MessageDto` backend shape includes `revisions: string[]` but the
  DB does not store the user's typed question text (confirmed via
  `backend/alembic/versions/0001_p1_baseline.py`: the `messages` table
  has `id, conversation_id, run_id, status, created_at, grounding,
  error`). **Consequence:** on refresh, the UI can restore the
  conversation, its assistant turns (grounding), pins, and rules —
  but not the user's question text. The DoD scope can be met
  ("restore the conversation, its pinned insights, and the draft rule");
  the user's typed text is a backend gap, not a P6b gap. Documented
  here; not fixed in P6b.

## Files

| File | Change |
|---|---|
| `frontend/src/lib/http.ts` | B1: `API_BASE` from page origin |
| `frontend/src/App.tsx` | B2: three-pane layout, no `workbench / catalog` view switch |
| `frontend/src/features/conversations/` (new dir) | B3 + B4: `rail.tsx` (list + select + New chat) |
| `frontend/src/features/chat/useChat.ts` | B3 + B10: URL-param restore, auto-follow |
| `frontend/src/features/chat/ChatPane.tsx` | B2: expose an `onSelectMessage` prop so the parent can auto-advance the workspace |
| `frontend/src/features/insights/rail.tsx` | B2 + B4: reduce to a pinned-insights section; drop "Draft rule" / "Evaluate" / `MetricsPanel` (they move to the rule workspace) |
| `frontend/src/features/workspace/WorkspacePane.tsx` | B8 + B9: stale-result marking, error contract surfacing |
| `frontend/src/features/rules/` (new dir) | B5 + B6 + B7: `workspace.tsx` (list + detail in one component) and `api.ts` (add `patchRule`) |
| `frontend/src/features/catalog/` | Delete after the refactor (its two files move to `features/rules/` and are replaced) |

## Task order

Each task lands with `npm run build` + `npm run lint` clean and the app
still working on `npm run dev`. The order is chosen so each step is
self-contained, not so the B-number looks pretty.

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
B1    B5     B6     B7     B10    B8     B9     B2+B3+B4
```

T1 is a prerequisite for everything else. T2–T5 fix the existing
catalog / workspace components in place. T6 restructures `App.tsx`
into three panes. T7 adds the new `features/conversations/` rail and
the URL-restore logic. T8 turns "New chat" non-destructive *by*
having a rail that lists every previous conversation.

## Task 1 — `API_BASE` from page origin (B1, finding #8)

**Files:** `frontend/src/lib/http.ts`

**Steps:**

1. Change the `API_BASE` const:

```ts
export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)
  ?? (import.meta.env.DEV ? "http://127.0.0.1:8000/v1" : `${window.location.origin}/v1`)
```

2. `npm run build` + `npm run lint` → clean.
3. `npm run dev` → the existing chat / catalog flows work as before.

**Acceptance (interactive session):**

- Open the app at `http://localhost:5173` (or whatever host you deploy
  to) → the network calls go to `<that origin>/v1/…`, not
  `http://127.0.0.1:8000/v1/…`.
- Dev mode still targets `http://127.0.0.1:8000/v1`.

## Task 2 — Rule workspace: drawer opens in every status (B5, findings #1 + #14)

**Files:** `frontend/src/features/catalog/CatalogPane.tsx`
(temporarily), and after this task moves to
`frontend/src/features/rules/workspace.tsx`.

**What to fix in `CatalogPane.tsx`** (before the move):

- The `open` / `showDetail` two-state bug. Replace with a single
  `openId: string | null` state. The render branch is
  `openId && detail → RuleDrawer`; otherwise the list. Closing sets
  `openId = null` (not `showDetail = false` while `open` stays set),
  so a re-click on the same rule re-fetches and re-opens.
- After a `Backtest` verb in the drawer, do not close the drawer —
  keep it open on the updated rule. `onChanged` should re-fetch the
  rule detail in place, not reset the view.

**Move to `features/rules/`:**

- `mkdir frontend/src/features/rules`.
- `cat frontend/src/features/catalog/api.ts > frontend/src/features/rules/api.ts`
  (same `rulesApi` shape, same path).
- Create `frontend/src/features/rules/workspace.tsx`: a single
  component that renders the rule list (top) and, when one is
  selected, the detail (the current `RuleDrawer` body). The component
  owns its own `openId: string | null` + `detail: RuleDetail | null`
  state. This is the rule workspace. Expose it as `RuleWorkspace` with
  props `{ refreshKey?: string }`.
- `App.tsx` (for now, until T6): replace the `CatalogPane` import with
  `RuleWorkspace` and keep the view switch — no layout change yet.
- Delete `features/catalog/` once the import above resolves.

**Acceptance (interactive session):**

- Open a rule card → the drawer/detail opens.
- Close it → open the *same* card → it opens again.
- Do `Backtest` on a draft → the detail stays open, status updates to
  `backtested`, metrics appear.
- Do `Approve` → status `approved`.
- Do `Deploy` → status `deployed`.
- In each of `draft`, `backtested`, `approved`, `deployed`, `rejected`,
  the detail is reachable by clicking the card.

## Task 3 — WHERE-clause editor (B6, findings #5 #13 UI half)

**Files:** `frontend/src/features/rules/api.ts`,
`frontend/src/features/rules/workspace.tsx`.

**Steps:**

1. Add to `rulesApi`:

```ts
patchWhereClause: (ruleId: string, where_clause: string) =>
  api.patch<RuleDetail>(`/rules/${ruleId}`, { where_clause }),
```

2. In the rule detail, add a clause-edit block:

   - A `<textarea>` bound to `rule.where_clause` (editable state,
     initialised from the detail).
   - A `Save clause` button that fires `patchWhereClause` on
     submit, re-fetches the detail on success.
   - Show the model's `rule.rationale` and `rule.assumptions`
     (they are already on the `RuleDetail` DTO; the drawer just
     renders them).
   - **Freeze-line behaviour (rule-lifecycle.md §45):** the editor is
     `disabled={rule.latest_backtest != null}` — after a backtest row
     exists, `PATCH {where_clause}` returns `409 RULE_ILLEGAL_TRANSITION`
     from the backend; we refuse to send it and show a short copy:
     "A backtest already exists against this clause. Re-draft from the
     insight to change the clause." (This is the P6a gate — we do not
     invent a way around it.)
   - On `SQL_REJECTED` (400) from the patch: render
     `error.message` + `error.details.offending_clause` (P6a added
     the `details` field; surface it here).
   - The card list updates after the patch (a `refreshKey` bump, or
     the component re-fetches the list on close of the detail).

3. `npm run build` + `npm run lint` → clean.

**Acceptance (interactive session):**

- A `draft` rule (no backtest run yet — `latest_backtest` is `null`):
  edit the clause, save → the textarea shows the new clause, the card
  in the list is unchanged in status, the rationale + assumptions are
  still visible.
- A `backtested` rule: the editor is disabled, the freeze-line copy
  shows ("A backtest already exists against this clause. Re-draft from
  the insight to change it."). See `rule-lifecycle.md` §freeze line —
  the clause and the backtest that justifies it are a matched pair.
- A `rejected` rule: same disabled state + same copy (it went through
  backtest, the freeze line applies).
- An `approved` rule: same disabled state + same copy (backtest →
  approved — the backtest row exists).
- A `deployed` rule: same disabled state + same copy (backtest →
  approved → deployed — the backtest row exists).
- A malformed clause (e.g. `SELEC * FROM transactionz`): the save
  button is disabled OR the patch fails with a visible
  `SQL_REJECTED` + `offending_clause` echo per P6a Task 2.

## Task 4 — Backtest detail with plain-English copy (B7, finding #9)

**Files:** `frontend/src/features/rules/workspace.tsx`.

**Steps:**

1. The detail already fetches `GET /v1/rules/{rule_id}/backtests/{bt_id}`
   on open (the old `useEffect` in `CatalogPane.tsx:58–71`, now in
   `workspace.tsx`). Make sure it fires in **every** status that has
   a `latest_backtest` (draft with a backtest, backtested, approved,
   deployed).
2. Render the four core metrics as a grid (already partly there in the
   old `RuleDrawer`, keep the layout) with one line of plain-English
   caption under each:

   | Metric | Caption |
   |---|---|
   | Precision | "Share of flagged transactions that are actually fraud" |
   | Recall | "Share of real fraud the rule catches" |
   | FPR | "Share of clean transactions the rule flags by mistake" |
   | Lift | "How much better than the base fraud rate (1.0× = no signal)" |

3. The "Deployed as <opaque-id>" line: replace with
   "Deployed at <HH:mm, DD Mon YYYY> — external rule
   `<external_rule_id>`", sourced from `rule.deployment.deployed_at`.
4. Show the `temporal_stability.earlier_slice` and `.later_slice`
   P/R as a two-column mini-table (already in the rail's
   `MetricsPanel`, port it).
5. `npm run build` + `npm run lint` → clean.

**Acceptance (interactive session):**

- The deployed rule's detail shows the deploy time + external id.
- The four captions render under the grid.
- For a rule with a backtest in any of `backtested`, `approved`,
  `deployed`, the stability mini-table + sample block are visible.

## Task 5 — Auto-follow the newest grounded turn (B10, finding #12)

**Files:** `frontend/src/features/chat/useChat.ts`.

**Steps:**

1. Currently `adoptMessage` (the on-terminal callback) already calls
   `onSelected({…})` with the new grounded turn. That is the
   auto-follow. The bug in the finding is that the *workspace* keeps
   the previous dirty edit — that is fixed by T6 below. The only
   change here is:
2. Add an `onFollow?: (messageId: string) => void` callback to
   `useChat`'s return (it is already the `onSelected` we pass
   through). The parent (the conversation panel) uses this to know
   when a new turn has grounded, so it can re-run the workspace's
   `materialize` for the new message — which resets the dirty edit
   to the agent's fresh SQL.
3. In `selectConversation`, when loading a past conversation,
   auto-select the newest grounded turn (`latest` is already
   computed at `useChat.ts:174–185` — wire it through `onFollow`
   too).
4. `npm run build` + `npm run lint` → clean.

**Acceptance (interactive session):**

- Ask a question → grounded answer → workspace auto-selects the
  newest turn (no manual click on the chat message).
- Edit the SQL in the workspace → ask a follow-up → the workspace
  auto-resets to the new agent's SQL (not the previous dirty edit).
- Click an older chat turn → the workspace switches to that turn's
  grounding.

## Task 6 — Stale-result marking + reset behaviour (B8, finding #7)

**Files:** `frontend/src/features/workspace/WorkspacePane.tsx`.

**Steps:**

1. Add a `stale: boolean` state. On a failed `materialize` / `execute`,
   set `stale = true`. On a successful `materialize` (fresh run) or
   when the selected message changes, set `stale = false`.
2. When `stale` is `true` and `results` is non-null, render the
   existing results table with a banner above it:
   `"Results from the last successful run — the query you edited is
   not what produced these rows."` Do not clear `results` on failure.
3. "Reset to agent query" must also clear the stale flag *and* any
   lingering error banner (the finding #7 "Reset clears nothing else"
   point). After reset, the SQL is back to the agent's and the
   workspace is not in an error state.
4. `npm run build` + `npm run lint` → clean.

**Acceptance (interactive session):**

- Successful run → results visible.
- Corrupt the SQL → click Re-run → the error banner shows the
  contract error (see T7), the results table stays visible with the
  "last successful run" banner.
- Reset to agent query → the stale banner and the error banner both
  clear, the SQL is back to the agent's.
- Re-run after reset → works, new revision, fresh results, stale
  banner gone.

## Task 7 — Error contract surfacing (B9, findings #2 #10)

**Files:** `frontend/src/features/workspace/WorkspacePane.tsx`,
`frontend/src/features/rules/workspace.tsx`.

**Steps:**

1. The `ApiError` class in `lib/http.ts` already parses
   `{error: {code, message, details}}` into `e.code`, `e.message`,
   `e.details`. The UI does not use `e.details`. Fix that:
2. In `WorkspacePane.tsx` (`execute` and `pin`), when the failure is
   an `ApiError` with `details`, render:

```
{e.message}

{e.details?.offending_sql ? `Offending SQL: ${e.details.offending_sql}` : null}

{retry hint per code}
```

   Retry hint per code (a small `Record<string, string>` map):
   `SQL_REJECTED → "Fix the SQL and re-run, or reset to the agent's
   query."`; `INTERNAL_ERROR → "The server failed. Try again."`
3. In `workspace.tsx` (rules) on a `patchWhereClause` failure and on a
   `backtest` / `approve` / `reject` / `deploy` failure, same shape:
   message + `details.offending_clause` / `details.offending_sql` +
   retry hint.
4. Remove the "Re-run failed." / "Draft failed." / "Backtest failed."
   string constants — they are gone; the message is always from the
   contract.
5. `npm run build` + `npm run lint` → clean.

**Acceptance (interactive session):**

- Break the workspace SQL (`SELEC * FROM transactionz`), Re-run →
  the error banner shows `error.message` from P6a's 400
  `SQL_REJECTED`, the `offending_sql` echoed, and the retry hint.
- Pin a broken-SQL insight → 4xx with the same shape (P6a gate).
- Attempt `Approve` on a non-`backtested` rule → 409 with the
  `message` from the contract, no 500.

## Task 8 — Three-pane layout + conversations rail + non-destructive New chat (B2 + B3 + B4, findings #6 #15)

This is the big one. It composes the existing components into the
target layout, adds the new `features/conversations/` rail, wires the
URL-restore, and makes "New chat" non-destructive.

**Files:** `frontend/src/App.tsx`,
`frontend/src/features/conversations/rail.tsx` (new),
`frontend/src/features/chat/useChat.ts` (URL-restore),
`frontend/src/features/insights/rail.tsx` (reduce),
existing `ChatPane` + `WorkspacePane` (moved into the conversation
panel).

**Steps:**

1. **New feature `features/conversations/rail.tsx`:**
   - Props: `{ activeId: string | null, onSelect: (id: string) => void,
     onNew: () => void, refreshKey?: string }`.
   - Fetches `chatApi.listConversations()` and renders a vertical
     list of `Conversation` cards (title = first grounded turn's
     grounded-explanation first line, or "New chat" if none;
     date, message count).
   - A **New chat** button at the top (or bottom) — calls `onNew`.
   - The active conversation is highlighted.
   - On mount and on `refreshKey` change: re-fetch.

2. **`useChat` URL-restore:**
   - On mount: read `new URLSearchParams(location.search).get("conversation")`.
     If present, `selectConversation(id)` (already exists at
     `useChat.ts:150–191`).
   - On `selectConversation` success: push
     `history.replaceState(null, "", `?conversation=${id}`)`.
   - On `newConversation`: push `history.replaceState(null, "",
     location.pathname)` (drop the param).
   - Do not use a router — one query param, one
     `history.replaceState` per transition.

3. **`App.tsx` restructure:**

   - Remove the `workbench | catalog` view switch.
   - Remove the `insightsKey` counter; replace with a single
     `refreshKey` that bumps on: a pin (from the workspace), a rule
     verb (from the rule workspace), a draft-rule (from the rail),
     a conversation switch. Any of these is a signal that the
     other panes' derived data may have changed.
   - Layout:

     ```
     <div className="flex h-svh">
       <ConversationsRail … />
       <main className="flex-1 min-w-0 flex flex-col">
         <ConversationPanel … />
       </main>
       <RuleWorkspace refreshKey={…} />
     </div>
     ```

   - `ConversationPanel` is a thin wrapper (new file,
     `features/conversation/pane.tsx`) that stacks `ChatPane` +
     "Pinned insights" (the reduced rail) + `WorkspacePane`. It
     receives `turns`, `busy`, `error`, `onSend`, `conversationId`,
     `selected`, `onSelected`, and the `refreshKey`. It is the
     seam that keeps the three sub-panes in sync.

4. **Reduce `features/insights/rail.tsx`:**
   - Remove `MetricsPanel` (it is now in the rule workspace).
   - Remove the "Draft rule" / "Evaluate" buttons on each card.
     Replace with a single **"View rule"** button when the insight
     already has a rule (via `rule_for[insight_id]`), or a
     **"Draft rule"** button that fires `rulesApi.draftRule` and
     bumps `refreshKey` (so the rule workspace's list refreshes and
     the FSM can open the new rule from there).
   - Remove the push-expand metrics behaviour (the `expanded` /
     `onToggleExpanded` props go away).
   - The rail is now: a pinned-insights list with a per-card
     "View rule" / "Draft rule" button. It does not own metrics.

5. **"New chat" non-destructive (B4, finding #15):**
   - The existing `newConversation` (useChat.ts:142–148) already
     does not delete the conversation on the backend — it only
     clears local state. Keep that.
   - The new conversations rail means every previous conversation is
     reachable by clicking it. That is the non-destructiveness.
   - No confirmation dialog required — the finding #15 concern
     ("no warning on New chat") is addressed by the rail's
     existence: the FSM can always see the old conversations and
     select them.

6. **`npm run build` + `npm run lint` → clean.**

**Acceptance (interactive session):**

- The three panes render. No top-bar view switch.
- New chat → ask a question → pin an insight → draft a rule → the
  rule appears in the right pane. The conversations rail now shows
  this conversation (highlighted) + any previous ones.
- Click "New chat" → the conversation panel clears (chat + workspace
  + pins empty), the rule workspace's list is unchanged (rules are
  global, not per-conversation), the conversations rail still lists
  the previous conversation.
- Click the previous conversation in the rail → its chat, pins, and
  draft rule (if any) restore from the API.
- Refresh the page (`location.reload()`) → the same conversation is
  restored (URL param + `selectConversation`), pins and rule are
  back.
- Navigate to `http://localhost:5173/?conversation=<a-real-uuid>`
  directly → that conversation loads.

## Final verification (after all tasks)

1. `cd frontend && npm run build` → clean.
2. `npm run lint` → clean.
3. `git status` → `docs/ux/` untracked, no stray `catalog/` tree.
4. **Interactive session** (`docs/phases/P6-error-contract-and-frontend-redesign.md` **P6b — DoD** checklist, walked live with the running stack):
   - Every B1–B10 item asserted.
   - The 15 findings in `../ux/fsm-evaluation-findings.md` either pass
     the same check as before (no regression) or are marked fixed /
     re-scoped in that doc.
5. **Chaos pass:** with the app running and a turn in-flight,
   `docker compose stop api` (or `kill -9` the uvicorn process) →
   assert the UI does not wedge (send re-enables, the last grounded
   turn's grounding is still visible, no exception text leaks into
   the DOM) → `docker compose start api` → assert state re-hydrates
   from the API (refresh or click a conversation).
6. Update the parent phase doc's checkboxes to match.

## Definition of done (P6b)

- B1–B10 all pass the interactive-session checks above.
- The rule drawer opens in every status and re-opens on every click.
- The WHERE-clause editor is present, wired, and honours the P6a
  freeze line.
- Refresh restores the session (conversation, pins, rule); "New
  chat" is non-destructive in practice because the rails let you
  get back.
- Error banners speak the contract (message + offending_* + retry
  hint), not "Re-run failed."
- Stale results are marked, never silently cleared.
- `npm run build` + `npm run lint` clean; no new dependencies;
  `docs/ux/*` untracked; `frontend/src/features/catalog/` gone (replaced
  by `features/rules/`).
