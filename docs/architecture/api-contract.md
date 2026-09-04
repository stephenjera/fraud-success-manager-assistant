# API contract v1 — REST + SSE

**Status:** accepted (frozen in P0, 2026-09-02). All routes, event names,
DTO shapes, and error codes below are *the* contract the reference frontend
builds against. Post-freeze, any change requires a new ADR; the ADR tree
(0001–0012) is unchanged by this freeze — the freeze records the *state*
of the contract, it doesn't change the *shape*.

**Drives:** ADR-0011 (API as a product, command/query SSE split), ADR-0012
(aim for prod where cheap), ADR-0006 (structured output, not prose),
ADR-0005 (the wall: the API is how `services/` enforces `core/`).

**Gap closures at the freeze pass (2026-09-02):** the four findings from
the FSM walkthrough (`e2e-walktalk.md`) and how this contract resolves
them. Each one is marked at the point of the contract it touches.

- **Gap A** — the *failed turn* shape. `GET …/messages/{mid}` is
  union-typed (`success` / `error` / `timeout`), not success-assuming.
  The message DTO gained `status`, nullable `grounding`, and `error`.
- **Gap B** — *pinning can grab the wrong revision.* `POST …/insights`
  requires `revision_id` + `sql`, not `message_id` alone. Pins the exact
  SQL the FSM saw.
- **Gap C** — *"eyeball the matches."* `POST …/backtest` and
  `GET …/backtests/{bid}` carry an explicit BacktestResult DTO, including
  `sample` rows.
- **Gap H** — *`rerun` is over-engineered.* `POST …/rerun` is
  synchronous (200), not a run/stream. A rerun is a deterministic
  re-execution, not a run.

## Conventions (apply to every route)

- **Versioned root.** Every route lives under `/v1/…`. One segment now,
  a rewrite later is the cost we avoid (ADR-0011).
- **Content on the wire.** All request/response bodies are
  `application/json`, UTF-8. SSE routes are `text/event-stream`. No
  HTML, no XML, no protobuf.
- **Lists use an envelope.** Any `GET` that returns a collection is:
  ```
  { "items": [ … ], "page": <int>, "page_size": <int>, "token": <str|null> }
  ```
  `token` is opaque, `page` is 1-based. First page: `{items, page:1,
  page_size, token:null}`. Subsequent: pass the returned `token` as
  `?token=…`. This is one wrapper now, and the only non-breaking way to
  go from "100 rows" to "cursor pagination" on a Catalog with thousands
  of rules.
- **Errors are one shape.** Every 4xx/5xx body is:
  ```
  { "error": { "code": <str>, "message": <str>, "details": <obj|null> } }
  ```
  `code` is a stable, machine-readable snake_case string. `message` is
  human-readable. `details` is optional; it's where request context
  (e.g. the offending SQL for a `SQL_REJECTED` error) lives. Stable
  codes the contract promises:

  | `code` | HTTP | meaning |
  |---|---|---|
  | `RUN_TIMEOUT` | 408 | the turn blew its wall-clock budget |
  | `SQL_REJECTED` | 400 | the validator (ADR-0002) rejected the generated SQL |
  | `RULE_ILLEGAL_TRANSITION` | 409 | state machine (ADR-0005) refused the verb |
  | `STATE_NOT_FOUND` | 404 | the resource does not exist |
  | `LLM_ERROR` | 502 | upstream LLM call failed or timed out |
  | `INTERNAL_ERROR` | 500 | anything else |

  The frontend has *one* error path. This is the direct payoff of "the
  API is the contract" (ADR-0011).
- **Auth boundary.** Spec §2 deliberately excludes auth/RBAC. The security
  model is a single-user local app behind a trusted origin. `created_by` /
  `approved_by` fields already exist so that adding an authn token in
  front of the routes does not rework the schema. Any future multi-user
  deployment adds a `Authorization` header check at the API edge — the
  *resources* and *verbs* here do not change.
- **CORS.** Allowlist-driven via `ORIGINS` in the env; never a `*`
  wildcard paired with `allow_credentials`. This prevents the classic
  "I didn't mean to allow cross-site credentialed reads" anti-pattern.
- **Idempotency on the lifecycle verbs.** `POST /rules/{id}/approve`
  called twice: the second call gets the current state (idempotent
  no-op) or a clean `409 RULE_ILLEGAL_TRANSITION` if the rule *moved* in
  between. The resource is the source of truth; the verb is an idempotent
  transition request.
- **DELETE exists.** `DELETE /v1/conversations/{id}`,
  `DELETE /v1/insights/{id}`, `DELETE /v1/rules/{id}`. Aiming for prod
  standards from day one; skipping them for a single-user prototype is a
  knowledge gap, not a save (ADR-0012).

## Command/query split for SSE (ADR-0011)

The split is the single most important design decision in this contract
and the whole reason "the API is the product" is true: **the state is
durable, the stream is a view of the state.** Any client can attach to a
run in flight, replay a finished one, or just poll — same data, no
different code path.

The *run* is a first-class readable resource: `GET /v1/runs/{run_id}`
returns its current status (a small object), `GET
/v1/runs/{run_id}/events` streams its event log, and the final grounded
answer is *always* reachable via `GET /v1/conversations/{id}/messages/{mid}`
because the `POST …/messages` command stored it before opening the stream.
A dropped or closed stream does not lose the answer; the answer is a
stored fact, and the stream is one (reconnectable) way to *see* it happen.

The run is backed by the LangGraph checkpoint (ADR-0003) — the graph
checkpoint *is* the run state, not a separate table the client has to
sync.

**Scope note:** the split applies to *runs that have something to stream*
— i.e. the agent turns. A *rerun* is not a run (Gap H, below): it is a
deterministic re-execute with no model call, and it returns
synchronously.

## Endpoints

### Meta

| Method & path | Returns | Notes |
|---|---|---|
| `GET /v1/meta/version` | `{version, git_sha, built_at}` | cheap, low-cost implementation (per spec §14 / ADR-0012). |
| `GET /v1/health` | `{status: "ok"}` | liveness. |
| `GET /v1/health/ready` | `{ready: bool, llm, db, langfuse}` | the "is it demoable" probe. |
| `GET /v1/schema` | the reflected reference schema (tables, columns, types, keys, row counts) | distinct from a conversation: it's a read of *reference* data, used by the workspace and by evals. |

### Conversations — the explore loop

| Method & path | Returns / body | Notes |
|---|---|---|
| `POST /v1/conversations` | `201 {conversation_id, created_at}` | new session. |
| `GET /v1/conversations` | envelope of `{conversation_id, created_at, last_active, message_count}` | the sidebar. |
| `GET /v1/conversations/{id}` | full conversation incl. its messages | a session detail. |
| `DELETE /v1/conversations/{id}` | `204` | cascade: conversation → its messages → its insights → the rules originating from those insights. |
| **`POST /v1/conversations/{id}/messages`** | **`201 {message_id, run_id, status: "running"}`** | **the command**: durably create the turn and start the run. Body: `{text}`. Returns immediately; the answer is not in this response — it's fetched (or streamed) under `message_id` + `run_id`. |
| `GET /v1/conversations/{id}/messages` | envelope of turn summaries | the transcript, durable. |
| `GET /v1/conversations/{id}/messages/{mid}` | **the message DTO** below (Gap A) | the canonical read of the answer. |
| `GET /v1/conversations/{id}/messages/{mid}/revisions` | envelope of `{revision_id, created_at, sql_preview, source}` | the tuning history. A `source` of `"agent"` (rev-1) vs `"rerun"` (rev-2+) distinguishes the model turn from human re-execute calls. |

**Message DTO (Gap A — union-typed success / error / timeout):**

```json
{
  "message_id": "m1",
  "run_id": "run-9c1",
  "status": "success" | "error" | "timeout",
  "created_at": "2026-…",
  "grounding": {
    "sql": "SELECT …" | null,
    "explanation": "…",
    "assumptions": ["…"],
    "tables_and_joins_used": ["…"],
    "flags": ["…"],
    "rule_proposal": {
      "title": "…",
      "where_clause": "amount > 5000 AND card_type = 'debit'",
      "rationale": "…",
      "assumptions": ["…"]
    } | null
  } | null,
  "error": {
    "code": "SQL_REJECTED" | "RUN_TIMEOUT" | ...,
    "message": "…",
    "details": null | { … }
  } | null,
  "revisions": ["rev-2", "rev-1"]
}
```

- `sql` is **nullable** (P5). A grounded answer that does not execute SQL
  — e.g. the model synthesises from prior turns or proposes a rule based
  on a pattern it identified — sets `sql` to null.  `grounding` is still
  populated; `error` is null.  This is **not** an error: the agent
  grounded its answer even without a query.
- On **failure** (a `run.error` on the stream): `grounding` is null,
  `error` is populated. The response is still `200` — the *body* tells
  the story, the status code only says "the message exists."
- `revisions` is a list of revision IDs, newest-first. `rev-1` is the
  original (from the model); subsequent revisions come from `rerun` calls
  (Gap H below).

This is the *canonical read* of the answer. The stream is one way to
*see* it happen; this GET is the durable fact. A dropped stream does not
lose the answer — **this endpoint is the answer** (ADR-0011,
"the state is the product").

### Runs — the streaming view

| Method & path | Returns | Notes |
|---|---|---|
| `GET /v1/runs/{run_id}` | `{run_id, conversation_id, message_id, status, created_at}` | `status ∈ {"running", "success", "error", "timeout"}` — the small durable object. |
| `GET /v1/runs/{run_id}/events` | `text/event-stream` of that run's events | **SSE.** Reconnect by `Last-Event-ID`. Any client — the reference frontend, `curl`, a future service — can attach without a different code path. |

#### SSE event set

All event bodies are **typed JSON** (ADR-0006) — never prose. The set is
*frozen* with this contract. Order is a property of the protocol, not of
one model's output.

| event | body (typed) | meaning |
|---|---|---|
| `run.start` | `{run_id, model, schema_version}` | a run has started. |
| `tool_call.start` | `{tool: "run_sql" \| "profile_column", args: <obj>}` | the agent is about to call a tool. |
| `tool_call.done` | `{tool, result_summary: <str>}` | the tool returned. |
| `message.delta` | `{delta: <str>}` | an incremental slice of the grounded answer. |
| `insight.suggested` *(optional, non-blocking)* | `{suggested: true, sql, headline_metric}` | the agent flagged a turn worth pinning. Non-blocking: the UI surfaces it, the FSM chooses whether to actually pin (a separate `POST /insights` call). |
| `run.done` | `{message_id, duration_ms, tokens_in, tokens_out}` | terminal, success. |
| `run.error` | `{code, message, details?}` | terminal, failure. Same shape as the error envelope. |

`run.done` / `run.error` / `run.timeout` are the only terminal events; a
well-formed stream emits exactly one of them.

### Insights — pin (spec §7.2)

| Method & path | Returns / body | Notes |
|---|---|---|
| `POST /v1/conversations/{id}/insights` | `201 {insight_id, …}` | body below. **Gap B: `revision_id` and `sql` are REQUIRED, not message-id-only.** |
| `GET /v1/conversations/{id}/insights` | envelope of insight cards | the right rail. |
| `GET /v1/insights/{id}` | full insight detail | the rail card. |
| `PATCH /v1/insights/{id}` | `200 {insight_id, …}` | body: `{sql?, explanation?}` — edit the pin before drafting. |
| `DELETE /v1/insights/{id}` | `204` | cascade: the rules with `source_insight_id = {id}`. |
| `POST /v1/insights/{id}/draft-rule` | `201 {rule_id, draft_where, rationale, assumptions}` | the pin → draft bridge. Enforces "a rule can only originate from a pinned insight" (spec principle 5). FSM-explicit (you fired it), agent-generated (the content). |

**Insight pin DTO (Gap B, P5 rule fields):**

```
Body: {
  "message_id": "m1",
  "revision_id": "rev-2",              // REQUIRED — the exact revision being pinned
  "sql": "SELECT … WHERE amount > 5000 AND card_type = 'debit'",  // REQUIRED
  "explanation": "…",                  // optional
  // P5: model-proposed rule fields (all optional, core/rules validates clause)
  "rule_title": "…",
  "rule_where_clause": "amount > 5000 AND card_type = 'debit'",
  "rule_rationale": "…",
  "rule_assumptions": ["…"]
}
```

- `rule_where_clause` — optional (P5). If present, the server runs it
  through `core/rules.validate_where_clause` before storing.  Allows the
  model to propose a rule without SQL — the clause is the gated
  property (ADR-0005 wall).  When the FSM later fires
  `POST /v1/insights/{id}/draft-rule`, the service prefers this stored
  clause over `derive_where_clause(sql)`.
- `sql` — **required.** The client *proves* to the server "I'm pinning
  this SQL I'm looking at." The server stores it verbatim. This is a
  stronger audit trail than a server-side "look up the live revision."

Consequence: the insight is tied to a *revision*, not a *message*. A
message can have many revisions; only the one the FSM chose to pin is the
one the rule will be built from.

### Rules — the lifecycle (spec §7 state machine)

| Method & path | Returns / body | Notes |
|---|---|---|
| `GET /v1/rules?status=…&created_by=…` | envelope of rule cards | **the Catalog.** Cross-conversation, filterable (spec §13). |
| `GET /v1/rules/{id}` | full rule detail | SQL, provenance, latest backtest, deployment record. |
| `PATCH /v1/rules/{id}` | `200 {rule_id, …}` | body: `{where_clause?, title?}` — edit-and-own on the rule (spec §7.1). **`where_clause` after a backtest row exists: `409 RULE_ILLEGAL_TRANSITION`** (the freeze line, [rule-lifecycle.md](rule-lifecycle.md); `title` stays editable). |
| `DELETE /v1/rules/{id}` | `204` | cascade: the `backtest_results` and `deployment_record` for the rule. |
| **`POST /v1/rules/{id}/backtest`** | **`201 {the BacktestResult DTO, below (Gap C)}`** | **deterministic, never LLM** (spec §7.4). The FSM fires it; `core/backtest.py` runs it; the LLM has no path to it. The ADR-0005 wall made visible: the FSM is the only trigger, the math is in `core/`, and the rule cannot reach `backtested` without a row in `backtest_results`. |
| `GET /v1/rules/{id}/backtests` | envelope of backtest history | tuning runs + the §10.4 drift comparison. |
| `GET /v1/rules/{id}/backtests/{bid}` | **the BacktestResult DTO (Gap C)** | one run. |
| `POST /v1/rules/{id}/approve` | `200 {rule_id, status: "approved", approved_at, approved_by, rationale}` | FSM-explicit action → `approved`. Body: `{rationale, actor}`. |
| `POST /v1/rules/{id}/reject` | `200 {rule_id, status: "rejected", rationale, actor}` | FSM-explicit action → `rejected` (terminal, from `backtested`). |
| **`POST /v1/rules/{id}/deploy`** | `201 {deployment_id, external_rule_id, …}` | FSM-explicit, from `approved` only. Assembles the payload (spec §9) via the mock `core/rule_engine.py`, returns the `DeploymentRecord` + fake external ID. |
| `POST /v1/rules/{id}/disable` | `200 {rule_id, deployment_id, disabled_at}` | post-deploy op; the `RuleEngineClient.disable_rule` (spec §9). P2. |
| `GET /v1/rules/{id}/deployment` | the current `DeploymentRecord` | `get_rule_status` (spec §9). |

**BacktestResult DTO (Gap C — "eyeball the matches"):**

```json
{
  "backtest_id": "bt-…",
  "rule_id": "r-…",
  "created_at": "2026-…",
  "window": "full window" | "custom",
  "metrics": {
    "precision": 0.0, "recall": 0.0, "false_positive_rate": 0.0,
    "baseline_fraud_rate": 0.0, "lift": 0.0
  },
  "confusion_matrix": { "tp": 0, "fp": 0, "fn": 0, "tn": 0 },
  "coverage": {
    "matched_count": 0, "total_rows": 0, "total_fraud": 0, "support": 0.0
  },
  "temporal_stability": {   // spec §8
    "earlier_slice": {"precision": 0.0, "recall": 0.0},
    "later_slice":   {"precision": 0.0, "recall": 0.0}
  },
  "sample": {
    "count": 5,
    "columns": ["id", "amount", "mcc_code", "card_type", "…"],
    "rows": [[…], […]]
  }
}
```

- `sample` is the "I don't trust aggregates, show me the rows" case.
  The FSM will eyeball these before approving. (The orphaned
  `compute_backtest` in the current `db.py:174` already produces
  `sample_matched_columns` + `sample_matched_rows`; the gap was that
  they weren't an explicit part of the contract.)
- Every field is *deterministic*. No field in this DTO is generated by
  an LLM. The ADR-0005 wall is visible: the FSM triggered the backtest
  (a command), `core/backtest.py` computed it, and the LLM has no path
  into it.

### Re-run (edit-and-own, spec §7.1)

| Method & path | Returns / body | Notes |
|---|---|---|
| **`POST /v1/conversations/{id}/messages/{mid}/rerun`** | **`200 {message_id, revision_id, result, flags}`** — synchronous (Gap H) | **Deterministic re-execute of the edited SQL, no LLM call.** Body: `{sql}` (the FSM's edit). Reuses the validator and flags (ADR-0005) so the edit is checked exactly like the agent's draft. |

**Re-run (Gap H — sync, not a run):**

```
Body:  { "sql": "SELECT … (the edited version)" }

Response 200:  {
  "message_id": "m1",
  "revision_id": "rev-2",
  "result": {
    "columns": ["…"],
    "rows": [[…], ...],
    "row_cap": 100,
    "truncated": false
  },
  "flags": ["…"]
}
```

- **No run, no stream.** A rerun is a *deterministic re-execute* with no
  model call. There is nothing to stream; the answer is the result set.
- **Still durable.** The revision is a first-class thing: after the call,
  `GET …/messages/{mid}` returns `revisions: ["rev-2","rev-1"]` — the FSM
  can always come back and see the history.
- **The ADR-0005 wall is still enforced.** The SQL still goes through
  `validate_sql` (sqlglot) and `flags` (sanity). The *wall* is the same;
  only the *transport* (run/stream) drops. This is a **deletion**, not an
  add.
- **Consequence for the message DTO:** `revisions` is a list of revision
  IDs, newest-first. `rev-1` is the original (from the model); rev-2,
  rev-3, … come from reruns. The insight pin (Gap B) references the
  revision *by ID*.

## Deliberately not endpoints (the *no* matters)

- **No `POST /v1/…/evaluate` that the *model* invokes.** Backtesting is
  a command *the FSM fires* and the agent has no path to it (ADR-0005,
  spec §7.4). Making it a model-callable route would re-open the very
  hole the ADRs close.
- **No eval-suite routes** (`GET /v1/eval/…`). Eval is `make eval`, a dev
  tool (ADR-0008, spec §14). A product route it doesn't deserve.
- **No `GET /v1/rules/{id}/chat` or similar.** The agent has no path into
  the rule lifecycle; the *rule* can only be reached from an insight, and
  the *insight* from a message. The state machine is structural, not a
  graph of model calls.

## Security surface (the *designed-out* vs. *explicitly deferred* line)

**Designed out (real, in scope):**
- **Write escalation / SQLi — structural.** The agent connects as
  `reference_readonly` (ADR-0007) and does not have write privilege;
  sqlglot (ADR-0002) is defense-in-depth on top, the *role* is the floor.
  Spec §11.1 stops being aspirational.
- **XSS — our actual risk, because the strings we persist are rendered
  later.** The vectors are the LLM's `explanation` / `assumptions` and
  the free-text reference cells (merchant descriptions). The API
  discipline that keeps rendering safe is exactly "return data, never
  HTML" (ADR-0011 consequence):
  - correct `Content-Type: application/json` on every response — never
    reflect a user string back as an HTML response body;
  - the contract carries **plain strings**, so a compliant client renders
    them as text nodes;
  - **frontend rule:** no `dangerouslySetInnerHTML` / `innerHTML` on any
    LLM- or data-derived string in `features/`; if markdown is ever
    wanted, a strict allow-list sanitizer, not raw interpolation.
- **CORS — pin it to an allowlist** (above). Never `*` + credentials.
- **Resource exhaustion on the two expensive ops.** A turn has a
  wall-clock budget (in addition to the existing `_RECURSION_LIMIT = 25`);
  a statement has a real timeout (Postgres `statement_timeout`, not the
  no-op `PRAGMA query_timeout` in db.py:77). A per-conversation
  concurrency cap is our rate limit at this scale.
- **Secrets never leave the server.** LLM / Postgres / Langfuse keys are
  not in any response body and not logged. A *specific* one to review:
  the Langfuse callback adapter captures the trace payload — a request
  body with a key in it would ride along in the span.

**Explicitly deferred (a boundary, not solved):**
- **AuthN / AuthZ.** Spec §2, §15. A stated single-user boundary. If
  multi-user, the authn token sits *in front of* the routes; the
  resources and verbs do not change.
- **CSRF** — low relevance without cookie auth; a `SameSite` / token
  decision *when* that comes.
- **WAF / rate-limit tiers** — the turn + statement budgets above are
  the stand-in.

The one-sentence version: **we structurally guarantee the write-side
(roles) and we return a shape that can only be rendered safely (data,
not HTML); we explicitly do *not* pretend to be a hardened multi-tenant
web app, and the ADR tree says so.**

## Walkthrough and the headless test

The contract is *exercised* in `e2e-walktalk.md` — the FSM driving
every endpoint in the intended order, with the expected response shape
at each step. That doc is the specification of a headless script
(`backend/scripts/e2e_walktalk.py`, P1 deliverable) that walks through
the same calls and asserts the shape of the responses. If a response
shape disagrees with this contract, the walkthrough fails — and that's
the test. The shape here is what the script holds the server to.

## Frozen (P0 freeze, 2026-09-02)

The shape is frozen: every route, the split, the versioning, the
envelope, the error shape, and the four gap closures above.

The event names and error codes listed in this doc are **final** as of
this freeze. A post-freeze change to a name is a *sed-able diff*, not a
rewrite — the shape is the design work. This doc is where the shape
lives; the names are the cheap one-line edits.

**What the freeze does to the rest of the docs:**
- ADRs 0001–0012 stay `proposed` — the freeze is *this* contract, not
  the whole ADR tree. P0's DoD ("flip all 12 to accepted") still holds;
  this contract flip is *part of that*.
- `00-roadmap.md` / P1 DoD: the E2E walkthrough
  (`e2e-walktalk.md`) is now a named deliverable; the script at
  `backend/scripts/e2e_walktalk.py` is the headless implementation.
- `api-contract.md` is the *only* doc in `architecture/` that is
  `accepted` at this point; the other seven are still `proposed`
  stubs awaiting the same freeze pass.
