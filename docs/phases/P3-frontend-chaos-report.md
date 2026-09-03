# P3 — Frontend chaos / robustness report

**Status:** completed, 2026-09-03. One real bug found, fixed, and re-verified.
Two open notes for judgment. All other attacks held up or are by design.

The P3 DoD in `P3-frontend.md` covers the *happiest* path: the four features
exist, the wireframes render, the SSE frames are consumed, the wall is
honored. This doc is the other half — what happens when the machine under
your feet goes away mid-interaction, or when the FSM types a DROP into the
SQL field on purpose. Not a replacement for the DoD, a complement.

**Scope note:** chaos is done in the UI, at the browser, with the stack
already running (vite :5173, uvicorn :8000, Postgres :5433, Ollama :11434).
No auth (spec §15, deferred), no load test, no fuzzing of the LLM prompt
itself — those live in P4 (`P4-hardening-and-docs.md`).

## What was attacked

The sequence below is roughly "increasingly mean." A round is done when one
of: the UI wedges, an error is visible to the FSM, or the state is provably
unchanged. A round that hits none of those is a "held up."

| Round | Attack | Result |
|-------|--------|--------|
| A | `kill -9` the whole uvicorn process group while a chat run is streaming SSE | **Wedged** pre-fix. See below. |
| B | `docker stop postgres` mid-run (backend alive, DB gone during SQL execution) | Recovered post-A-fix. |
| C | Type `DROP TABLE transactions`, `DELETE FROM …` stacked, `INSERT INTO …` into the workspace, hit **Re-run** | All blocked, clean 4xx in the error card. |
| D | `SELECT count(*) FROM appstate.rules` via Re-run — try to read the app's own state out of the read-only data role | Blocked, permission denied surfaced in the error card. |
| E | `SELECT rolname, rolcanlogin, rolsuper FROM pg_roles` via Re-run — info-leak probe | Allowed (see "by design" below). |
| F | Invalid rule transitions: `POST /rules/<draft>/approve`, `POST /rules/<backtested>/deploy`, `POST /rules/<rejected>/deploy`, `POST /rules/<uuid>/approve` on a fresh uuid | All 409 / 404 with structured `error.code`. |
| G | Approve with `{}` body — missing `actor` + `rationale` | 400 with per-field detail. |
| H | `pg_settings`, `current_user`, `session_user`, `current_schema()` | Returned. No secrets in the surface set. |
| I | CORS: fire a 500 via Re-run, inspect response headers for `Access-Control-Allow-Origin` | Header present (see "not a bug"). |

## The one bug that was real: mid-stream SSE wedge

**Symptom.** Ask a question. The run starts, at least one SSE frame arrives,
the assistant bubble has begun. Then the backend dies mid-flight
(process SIGKILL'd, or the network drops underneath it). The UI stops
showing progress, the assistant bubble is empty of text, and **Send is
permanently disabled** — the FSM has to hard-refresh to get back.

No console-visible error. No in-app "Connection lost" banner. The turn just
… stops. The FSM has no handle to recover from.

**Root cause.** `frontend/src/features/chat/useChat.ts:108`, the
`onTerminal` handler.

```ts
// pre-fix shape (abridged)
onTerminal: async (terminal) => {
  if (terminal === "error") {
    patchTurn(asstKey, (t) => ({ ...t, status: "error" }))
  }
  if (message_id) await adoptMessage(cid, message_id, asstKey)  // ← throws when backend is gone
  setBusy(false)                                                    // ← never reached on throw
}
```

`fireTerminal` in `frontend/src/features/chat/api.ts:73` calls the handler
fire-and-forget — the returned promise is discarded. When
`adoptMessage`'s `GET /conversations/{cid}/messages/{mid}` rejects because
the backend is gone, the rejection is unhandled (Node / browser logs the
`unhandledrejection`; the UI doesn't see it), and the `setBusy(false)`
after it never runs. `busy` is the gate on the Send button at
`frontend/src/features/chat/ChatPane.tsx` — so the button stays
disabled, forever.

**Fix.** `frontend/src/features/chat/useChat.ts:108`. The adopt is
wrapped; the `catch` writes a `STREAM_LOST` error onto the turn, the
`catch` also sets the pane-level error banner. `setBusy(false)` now runs
on every path.

```ts
onTerminal: async (terminal) => {
  if (terminal === "error") {
    patchTurn(asstKey, (t) => ({ ...t, status: "error" }))
  }
  if (message_id) {
    try {
      await adoptMessage(cid, message_id, asstKey)
    } catch (e) {
      patchTurn(asstKey, (t) => ({
        ...t,
        status: "error",
        error: {
          code: "STREAM_LOST",
          message: e instanceof Error ? e.message : "Connection lost.",
        },
        text: t.text || "Connection lost before the turn finished.",
      }))
      setError(e instanceof Error ? e.message : "Something went wrong.")
    }
  }
  setBusy(false)
},
```

**Verified.** Same attack, same kill, same timing. Post-fix, the assistant
bubble shows **"Connection lost before the turn finished."** with the
`STREAM_LOST` error code; the pane-level banner shows `Error. Failed to
fetch`; **Send re-enables** the moment the FSM types a new question.
Round B (Postgres death) hits the same path through a different trigger and
recovers identically — one fix covers both.

`npm run build` is green after the change (TypeScript, Vite, ESLint).

## What held up

Not a checklist of what *should* survive — these were the things I
actually tried to break, in the browser, with a real stack.

**SQL injection through Re-run (`workspace`).**
`DROP TABLE transactions`, `DELETE FROM …` stacked on a `SELECT`, and
`INSERT INTO …` each landed and rejected. The error card shows
`SQL_REJECTED — Read-only SELECT only (found 'DROP')` (and matching
variants). The rejection is two-layer:
`backend/app/core/sql_validator.py` first, then the
`reference_readonly` role in Postgres as the enforcement floor.

**Scope escalation via Re-run.**
`SELECT count(*) FROM appstate.rules` and
`SELECT count(*) FROM appstate.messages` both rejected with HTTP 500,
message `permission denied for schema appstate`. That's the *correct*
rejection — the role can't see the schema. (See "Open notes" about the
5xx code label.)

**pg_catalog probe.**
`SELECT rolname FROM pg_roles` is permitted and returns. That's fine —
role names are catalog metadata the role is intended to see, and there is
no password column in the read surface. `current_user`, `session_user`,
and `current_schema()` confirm the executor is
`reference_readonly` in `reference`.

**Invalid rule transitions.**
Every illegal jump is 409 with `RULE_ILLEGAL_TRANSITION`, including the
terminal-state ones. Every non-existent id is 404
`STATE_NOT_FOUND`. Missing fields on `approve` is 400 with per-field
error detail.

**CORS on failures.**
`Access-Control-Allow-Origin` is present on 404s, 409s, and 500s alike.
The `CORS middleware wraps the app` claim in `../architecture/api-contract.md`
holds under failure, not just on the happy path.

## By design, not bugs

- **`pg_catalog` is readable from the workspace.** Role names,
  `pg_settings` for non-secret settings, `current_user`. This is what a
  read-only data role is *for* — a fraud analyst who needs to know what
  schemas exist. There are no password or DSN columns in the
  `reference_readonly` read surface. If the product requirement is "never
  any `pg_*` access," add a keyword block to
  `backend/app/core/sql_validator.py:38` — one-line change. Not done,
  because we don't have that requirement.
- **`5xx` is `code:"INTERNAL_ERROR"`.** Some expected rejections
  (permission denied, empty body on a required-field) surface as 5xx
  with `INTERNAL_ERROR`. This is a code-taxonomy choice, not a bug.
  The FSM gets a message + status; the *label* is just conservative.
  If the product wants precise 4xx/403 mapping on these, the backend
  side needs a small mapping table in
  `backend/app/api/errors.py`.

## What this doc does not cover

- **Prompt-level attacks** on the LLM ("ignore your system prompt").
  That's P4's `make eval` — ADR-0004 / spec §14.
- **Load / concurrency** chaos. Out of scope for a single-operator
  reference implementation. Spec §15.
- **Multi-tenant / auth chaos.** Spec §15 deferred explicitly.
- **`New chat` mid-kill** and other rare timing interleavings — none
  reproduced in this session, but a proper regression test
  (`frontend/src/features/chat/useChat.test.ts` or a Playwright script
  under `frontend/e2e/`) should lock in the mid-kill recovery case.
  See "P4 follow-up."

## P4 follow-up

Two items land in `P4-hardening-and-docs.md` when P4 is on.

1. A regression test for the `STREAM_LOST` recovery path.
   A Playwright spec (or a `useChat.ts` test that stubs `fetch` to
   fail mid-stream) that: (a) starts a turn, (b) kills the backend
   mid-run, (c) asserts Send re-enables and the assistant bubble shows
   a `STREAM_LOST` error.
2. A `sql_validator.py` unit test for an explicit `pg_catalog` policy —
   whichever of "allowed" or "blocked" is the chosen product position.
