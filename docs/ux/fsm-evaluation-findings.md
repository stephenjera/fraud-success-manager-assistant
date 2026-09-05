# FSM tool — evaluation findings (live test, 2026-09-05)

Perspective: non-technical Fraud Success Manager. App: http://localhost:5173, backend :8000.

## Status legend
- [BUG] = broken behavior
- [UX]  = clunky / confusing but functional
- [RISK]= works, but fragile in a real deployment

---

## Findings

### 1. [BUG] Re-clicking the same rule in Rules Catalog does nothing
- Where: `frontend/src` CatalogPane (drawer)
- Symptom: open a rule drawer → "Back to list" → click the SAME rule again → nothing happens.
- Root cause found: close handler calls `setShowDetail(false)` but never resets `open`; the fetch effect
  depends on `[open]`, so a second click with the same value is a no-op. Workaround is clicking a
  different rule first.
- Severity: high — the FSM's core "look at this rule" loop silently breaks after the first drawer close.
- **Status: FIXED (P6b/B5)** — one rule workspace; re-clicking a rule always reopens its detail.

### 2. [BUG] Failed Re-run shows a useless error — the real error is hidden twice over
- Symptom: break the workspace SQL (`SELEC * FROM transactionz`), click Re-run → UI shows only
  "Error. Re-run failed." No reason, no SQL echoed, no hint of what to fix (screenshot 03).
- Chain (curl-verified with Origin: http://localhost:5173):
  1. Backend returns **500** (not 400 — see finding 3), body *does* contain the useful
     diagnostic (`"Required keyword: 'expression' missing … Line 1, Col: 12"`).
  2. **That 500 response has NO CORS headers** (no `access-control-allow-origin`), while
     200s and 4xx responses do → browser `fetch` throws an opaque network TypeError and
     the error body (with the diagnostic) is never readable → finding 4, the root cause.
  3. Frontend catch-all maps it to "Re-run failed."
- FSM consequence: cannot self-correct; would have to ask the model to guess.
- Fix directions: (a) 400 SQL_REJECTED with the validator message (finding 3);
  (b) CORS headers on error responses (finding 4); (c) UI surfaces `error.details`.
- Severity: high.
- **Status: FIXED (P6a/A2 + A1 + P6b/B9)** — unparseable SQL now returns 400 `SQL_REJECTED`
  readably; the UI surfaces `error.message` + `details.offending_sql` with Reset.

### 3. [BUG] Invalid SQL returns HTTP 500 INTERNAL_ERROR instead of 4xx
- Curl replay of POST …/messages/{id}/rerun with `{"sql":"SELEC * FROM transactionz"}`:
  `500 {"error":{"code":"INTERNAL_ERROR","message":"Unexpected server error.","details":
  {"error":"Required keyword: 'expression' missing for <class 'sqlglot...Mul'>. Line 1, Col: 12"}}}`
- Expected: 400/422 SQL_REJECTED (the endpoint code has a SqlRejected path — the parse error is
  apparently escaping it into an unhandled exception).
- Consequence: clients can't distinguish "your SQL is bad" (4xx, retryable/editable) from
  "server is broken" (500). The frontend's generic error (finding 2) is downstream of this.
- Bonus instance of the same 500-instead-of-400 pattern: GET /v1/conversations/{bad-uuid}
  returns 500 INTERNAL_ERROR with a psycopg "invalid input syntax for type uuid" leak
  (curl, Sep 05 08:43) — should be 404 STATE_NOT_FOUND.
- **Status: FIXED (P6a/A2 + A3)** — invalid SQL → 400 `SQL_REJECTED`; non-UUID ids →
  404 `STATE_NOT_FOUND`; no exception text in either body.

### 4. [BUG — ROOT CAUSE] Every 500 from the API lacks CORS headers, so in the browser every 500 looks like a random network failure
- Curl with `Origin: http://localhost:5173` (app's own origin, from backend `.env` ORIGINS):
  - `POST …/rerun` invalid SQL → **500, headers: date/server/content-length/content-type only —
    NO `access-control-allow-origin`** (curl, Sep 05 08:42).
  - same call with valid SQL → 200 **with** `access-control-allow-origin: http://localhost:5173`,
    `access-control-allow-credentials: true`, `vary: Origin`.
  - 404 (ApiError, valid UUID) → **has** CORS headers; 400 (validation) → **has** CORS headers;
    500 (psycopg uuid error) → **no** CORS headers.
- So it is not a per-route bug: **the class of responses** that lacks headers is exactly "500 from
  an unhandled exception". All 4xx (handled inside the app) are fine.
- Root cause verified in installed sources (FastAPI 0.141.1, Starlette 1.6.0):
  `FastAPI.build_middleware_stack` extracts the generic `Exception`/500 handler and hands it to
  **ServerErrorMiddleware, which wraps the outside of user middlewares (CORSMiddleware)**.
  Exceptions handled there are sent with the raw outermost `send`, bypassing CORSMiddleware
  entirely → no CORS headers. ApiError/4xx are handled by `ExceptionMiddleware` *inside*
  CORSMiddleware → headers present. (Starlette's CORS `send` wrapper would add the headers,
  but it never sees the 500.)
- Impact: in the browser, every 500 (bad SQL, bad UUID, any unexpected error) is unreadable →
  generic "Re-run failed."-style messages everywhere; also breaks any future non-browser client
  relying on CORS semantics. This is the upstream cause of finding 2.
- Fix directions: add CORS headers in the 500 error handler (`errors.py::_internal`), or apply
  CORSMiddleware as the outermost middleware, or convert expected failures (SQL parse, bad UUID)
  into 4xx so they stay inside ExceptionMiddleware.
- **Status: FIXED (P6a/A1 + A2 + A3)** — the 500 handler now emits `access-control-allow-origin`
  + credentials for allowed origins (and no exception text in the body); expected failures (bad
  SQL, bad UUID) are also converted to 400/404 so they stay inside ExceptionMiddleware.
- Severity: high.

### 4a. [NOTE] The "two POST /rerun in the network log" is NOT a double-fire bug
- Request 23 (200) was the workspace's auto-materialize: selecting a grounded answer runs the
  agent's SQL once (creates a revision, `1826e4a8…`) — expected behavior on first render.
- Request 25 (failed) was my Re-run click with the corrupted SQL → the CORS-blocked 500 above.
- So: one click = one request. No double-fire. (Retracted earlier hypothesis.)

### 5. [UX] Seeded rules are all "Unnamed rule"
- Catalog cards, drawer heading: every seeded rule (deployed AND rejected) is titled "Unnamed rule".
- FSM cannot tell rules apart without opening each drawer and squinting at SQL.
- **Status: FIXED (P5 backend + P6b/B6)** — `draft-rule` now carries the model's `rule_title`
  (P5); the rule workspace renders it as the heading instead of "Unnamed rule".

### 6. [BUG] No persistence — whole UI state is wiped
- Chat, workspace (SQL + results), and the Insights rail were all empty after navigating away and back
  (observed mid-session; earlier session state survived a reload, so persistence is inconsistent).
- Severity: high — the FSM's working set (queries, pins, drafts) is fragile; a refresh can destroy it.
- **Clean repro confirmed (2026-09-05):** fresh chat → one question → grounded answer in workspace (Mastercard/Visa/Amex/Discover table) → `location.reload()` → chat empty, workspace empty, Insights rail "No pinned queries yet". The turn existed on the backend (run id 79abe33d-bf55-4c60-9090-cc3db41283d5 visible pre-refresh) but the UI has no way back to it. Screenshot: 06-refresh-wipe.png.
- **Status: FIXED (P6b/B3)** — refresh restores the conversation from the API; the selected
  conversation is persisted in the URL (`?conversation=<uuid>`) and re-hydrated on load.

### 7. [UX] Stale results stay visible under a failed Re-run
- After the failed rerun, the old (previously successful) result table remains with no marker that
  it is stale. Risk of acting on results that don't match the query shown above them.
- Same family: after **Reset to agent query** the SQL is restored but the red "Error. Re-run
   failed." banner stays — the error now describes a query that isn't even shown anymore.
   Reset clears nothing else and does not auto-rerun (Re-run works fine after: new revision,
   fresh results — verified 2026-09-05).
- **Status: FIXED (P6b/B8)** — a failed re-run marks the previous result stale (banner + label)
  and shows the real `error.message`; Reset clears the stale mark and the error banner.

### 8. [RISK] Frontend hardcodes API base to 127.0.0.1
- `frontend/src/lib/http.ts`: `VITE_API_BASE ?? "http://127.0.0.1:8000/v1"`; no `.env` in repo.
- CORS allowlist is `http://localhost:5173` (page origin). Works today, but 127.0.0.1 vs localhost
  mismatch is exactly the kind of thing that breaks the moment the app is served from a different
  host/port, and it's invisible to the FSM.
- **Status: FIXED (P6b/B1)** — `API_BASE` now derives from the page origin in production
  (dev fallback to `127.0.0.1:8000/v1` kept for local dev).

### 9. [UX] Deployed rule drawer shows weak stats
- Drawer for the deployed rule: "Latest backtest · full" with Lift 1.0× — looks like the rule does
  nothing, with no explanation that lift≈1 is the expected baseline value or that it's a mock.
- "Deployed as mock-rule-1dc053c9ba93" — opaque ID, no human rule name, no deploy date/time, no
  "who deployed / why".
- **Status: PARTIALLY FIXED (P6b/B7 + B6)** — the drawer now shows the full backtest (precision,
  recall, FPR, lift) with plain-English copy, the rule's human title (finding 5), and the deploy
  timestamp. "Who deployed / why" (actor + deploy rationale) has no backend field — re-scoped to a
  future auth/attribution feature, out of P6 scope.

### 10. [UX] Error copy is inconsistent / non-actionable
- Observed variants: "Error. Re-run failed." — flat, no next step. Compare with a good pattern:
  "Your SQL had a syntax error near column 12 ('SELEC'). Fix it or Reset to agent query."
- **Status: FIXED (P6b/B9)** — every error block now carries `error.message` + the offending
  clause/SQL + a concrete next step (fix the SQL, or Reset to the agent query).

### 11. [BUG] Pin insight has no guard — pins broken SQL as a valid insight
- Corrupted the textarea to `THIS IS NOT SQL` and **Pin insight still succeeded (HTTP 201)**.
  The stored insight is internally inconsistent: `sql: "THIS IS NOT SQL"` paired with the *real*
  agent explanation (Music Stores 38.89% fraud rate, 7/18 transactions).
- The insights rail now displays "THIS IS NOT SQL" as a pinned insight (verified in snapshot).
- FSM consequence: the insight is the artifact they share/act on; later re-running it fails with
  no context, and the explanation contradicts the stored SQL.
- → Disable Pin while SQL is dirty/unrun (or warn "modified, not re-run"); never pair an
  explanation with a different SQL than the one that produced it; validate SQL server-side on pin.
- Severity: high.
- **Status: FIXED (P6a/A6 + P6b/B9)** — pinning SQL that doesn't parse is rejected server-side
  with 400 `SQL_REJECTED` (no row created), and the UI surfaces the offending clause instead of
  a generic "Could not pin."

---

---

### 12. [UX] Workspace does not auto-follow a new turn's answer — it sits on the *previous, dirty* state
**As an FSM:** I asked a follow-up question and got a great answer in the chat — but the workspace in the middle *still showed the previous turn's broken, hand-edited SQL* ("THIS IS NOT SQL", Pin disabled). I almost concluded the new question failed. Only when I **clicked the new chat answer** did the workspace switch to the new query.
**What I saw:** After a new grounded turn completed, the workspace kept showing the old message's dirty textarea, old results table, and old revision history. The new answer's SQL/results only appeared after a manual click on the new chat message.
**Why it matters:** The header promise is "Ask, and the query lands in the workspace in the middle" — only true for the *first* question. On follow-ups the workspace silently goes stale and shows *my dirty edits*, which read like "the system's answer". No label says which turn the workspace is displaying.
**Fix:** auto-select the newest grounded message when a turn completes (or label the workspace: "Showing answer 2 of question 2 (unmodified / dirty)").
- Severity: medium (misleads about which turn is active; amplified by finding 11's dirty-state stickiness).
- **Status: FIXED (P6b/B10)** — the workspace auto-follows the newest grounded turn; an older
  turn can be selected by clicking it in the chat (labelled current vs stale).

---

### 13. [BUG — CRITICAL] "Draft rule" copies the query's WHERE clause verbatim — including `is_fraud = 1` (label leakage)
**As an FSM:** I pinned the "top fraud merchants" analysis, hit **Draft rule**, and the new rule's detection clause was:

    fl.is_fraud = 1 AND t.date >= '2019-10-01' AND t.date < '2019-11-01'

That clause *selects transactions that are already labeled as fraud*. As a detection rule it can never work on live traffic (new transactions have no label) — and yet its backtest reports **precision 1.0, lift 571** (labeled universe) / **lift 824** (full universe). A non-technical FSM reading those numbers would think this is a fantastic rule and deploy it.
**What's actually happening (verified against the API):**
- `POST /v1/insights/{id}/draft-rule` mechanically extracts the pinned query's WHERE clause as the rule. The model had generated a *real* rule proposal in chat — `mcc IN (5311, 5411, 5310, 5541, 5912) AND fraud_count_last_30d >= 8` with a rationale — but the drafted rule has `rationale: null` and the title is "Unnamed rule" (again, finding 5). The proposal and its rationale are thrown away.
- The docs (`docs/architecture/e2e-walktalk.md` step 15, `docs/architecture/rule-lifecycle.md` §46) make explicit the intended flow: draft → **FSM edits the WHERE clause** (`PATCH /v1/rules/{id}`, "this is the normal tune-the-clause flow") → backtest. **The UI has no rule editor at all** — `frontend/src/features/catalog/api.ts` has no `patch` call for `/rules/{id}` (grep-verified); the drawer shows the clause as read-only text. So the *only* path in the UI is draft → backtest the raw extracted clause.
- Backtest detail (`GET /v1/rules/{rule_id}/backtests/{bt}`) for this rule: precision 1.0, recall 0.13, fp 0, tp 177 — mathematically consistent with "the rule is just `is_fraud = 1` in October": it matches only the labeled-fraud rows in that window.
**Why it matters:** This is the heart of the product — turning an insight into a deployable detection rule. Right now it manufactures a circular rule (flag = "this is fraud because it is fraud"), shows it excellent evidence, and offers no way to fix the clause in the UI. It silently defeats the app's own guardrail (spec principle: evidence justifies the rule).
**Fix:** use the model's rule proposal (with rationale/assumptions) as the draft; or at minimum strip label columns from extracted clauses and refuse to backtest a clause that references the label table (`fl.is_fraud`); and ship the clause editor the docs promise.
- **Status: FIXED (P6a/A4 + A5 + P6b/B6)** — `validate_where_clause` now rejects the `is_fraud`
  label column; `draft-rule` on a circular clause returns 400 `SQL_REJECTED` and creates no rule
  row; the rule workspace exposes the clause editor (`PATCH /v1/rules/{id}`) the docs promise.
- Severity: **critical** (core value proposition; false confidence).

### 14. [BUG] After Backtest, the rule's detail drawer will not open — the results are invisible in the UI
**As an FSM:** I clicked **Backtest** on my new draft. It succeeded (card changed to "backtested · 1 backtest 0 deploys"). Then I clicked the card to read the precision/recall the docs say I'm supposed to see — **nothing opened**. Clicked again, clicked a third time: the card highlights (marked active) but no drawer, no metrics, no Approve/Reject buttons. The only place those numbers exist is the raw API.
**What I saw:** Drawer opens fine while the rule is still a *draft* (I read the clause there). After the backtest, the same card click does nothing. `GET /v1/rules/…` + `/backtests/{id}` return full metrics (precision, recall, confusion matrix, temporal stability, sample rows) — so it's a UI-only failure.
**Why it matters:** The FSM's whole job at this step is to decide approve vs reject based on evidence. If the evidence pane can't be opened, the workflow is dead in the water (I can only approve/reject blind — or not at all).
**Fix:** rule-card click should open the detail drawer in every status (draft/backtested/approved/deployed); show the latest backtest's metrics inside it.
- **Status: FIXED (P6b/B5 + B7)** — the rule workspace opens the detail drawer in every status
  (verified draft, backtested, deployed, rejected) and renders the latest backtest's precision,
  recall, FPR, and lift alongside Approve / Reject verbs.
- Severity: **high** (blocks the decision step of the core loop).

---

### 15. [UX] "New chat" silently discards the Insights rail — no way to revisit previous conversations
- Clicking "New chat" clears chat, workspace, **and** all pinned insights ("No pinned queries yet").
- The Rules Catalog survives (global state), but insights/conversations are per-chat and there is no conversation list, no switcher, no history — once you start a new chat, the previous working set is unrecoverable in the UI (backend still has it: /v1/conversations).
- For an FSM who builds rules over several sessions, this is a data-loss-feeling UX: pinning insights feels permanent, then it evaporates on "New chat".
- Severity: medium (no data destroyed server-side, but no recovery path in the UI; no warning on New chat).
- **Status: FIXED (P6b/B4 + B3)** — the conversations rail lists every prior conversation; "New
  chat" only switches the working set, the previous conversation (with its pins and rules) stays
  reachable in the rail.

## Root-cause split: backend design vs frontend under-use

- **True backend defects:** #4 (all 500s lack CORS headers — FastAPI ServerErrorMiddleware ordering),
  #3 (invalid SQL → 500 instead of 4xx), #13 core (`services/rules.py` falls back to
  `derive_where_clause(sql)` — a verbatim WHERE copy — and `validate_where_clause` does not
  reject the `is_fraud` label column; rationale comes back null).
- **Shared (backend + frontend):** #11 (`POST /insights` accepts any SQL — no server-side
  grounded/valid check), #5 (rules born from draft-rule carry null title → "Unnamed rule").
- **Pure frontend — the API already does it:** #6/#15 (backend persists conversations, insights,
  runs; `GET /v1/conversations` + message listing exist, UI never fetches them),
  #13 UI half (`PATCH /v1/rules/{id}` exists in the API but the UI has no clause editor),
  #14 (full backtest detail endpoint exists — precision/recall/lift/stability — UI never renders it),
  #9 (drawer shows a subset of available metrics), #1, #7, #8, #12.

**Bottom line:** the backend API surface is broader than the UI uses; the release-blockers split
into 3 backend root causes (CORS-500, 500-semantics, label-unsafe draft fallback) and a set of
frontend gaps where endpoints exist but the UI doesn't call them.

## Verified working (so far)
- Ask question → model grounds it: workspace shows SQL, results table, revision id, "Reset to agent
  query" appears when edited. ✔
- Backend rerun endpoint works end-to-end for valid SQL (curl). ✔
- Catalog: deployed vs rejected badges, drawer shows SQL, pinned-from insight, backtest stats. ✔
- Rule detail shows "Pinned from" with source SQL + insight id — good provenance. ✔
- CORS preflight on /v1/conversations returns proper allow-origin for http://localhost:5173. ✔

## Screenshots (in `docs/ux/screenshots/`)
- 01-initial.png, 02-workspace-permcc.png, 04-catalog-deployed.png, 05-catalog-after-backtest.png, 06-refresh-wipe.png

## Next tests planned
- [x] Failure path: invalid SQL → Re-run (done → findings 2,3,4,7,10)
- [x] OPTIONS preflight on the exact /rerun path (isolate finding 4) — done: preflight IS CORS-clean; the failure is the 500 *body* lacking CORS headers (finding 4)
- [x] "Reset to agent query" actually restores + reruns — restores agent SQL, no auto-rerun, stale error banner remains (finding 7); Re-run after reset works (fresh revision + results)
- [x] Pin broken-SQL result → does it pin garbage? — YES, pins it (finding 11)
- [x] Does the workspace follow new turns? — only after manually clicking the new chat answer (finding 12)
- [x] Draft rule → backtest → deploy round trip (partial): draft ✔, backtest ✔, **but** drafted clause is a leaky WHERE-copy (finding 13) and post-backtest drawer won't open (finding 14) — blocked before Approve/Deploy
- [x] New chat: catalog survives, chat+workspace+insights all cleared, no conversation history (finding 15)
- [x] Refresh page mid-conversation — clean repro of finding 6 (6-refresh-wipe.png)
