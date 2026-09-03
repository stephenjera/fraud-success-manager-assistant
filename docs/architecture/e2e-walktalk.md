# E2E walkthrough — FSM goes from zero to deployed rule

**Status:** frozen with the API contract at P0 freeze (2026-09-02). This
is the *specification of the headless test* — not the test itself. The
implementation is the P1 deliverable `backend/scripts/e2e_walktalk.py`.

**Drives:** ADR-0011 (command/query split, which this walkthrough
*verifies works*), ADR-0006 (structured output, which steps 5/7
assert are the typed object and not prose), ADR-0005 (the wall, which
steps 20/22 exercise by firing a deterministic verb and asserting the
response is shape-correct).

**Excludes:** model-content validation. This is an **API contract
test**, not a correctness test. If the server returns the shape we
promised (`api-contract.md`), the walkthrough passes, regardless of
whether the agent wrote a *good* SQL. The correctness of the agent's
SQL is the eval suite's job (`../architecture/eval-design.md`), not
this one.

## What this is / is not

**Is:** me, as the FSM, driving the API in the exact order a real user
would, with the expected response shape at each step. Each numbered
step is a `verify` in the future script.

**Is not:** a load test, a red-team pass, a spec of *correctness*
of the LLM's answer, or a spec of the LLM's *strategy*. It is the
shape assertion.

## The walk

### Phase 1 — session start

```
1.  GET  /v1/health/ready
    → 200 {ready: true, llm: {configured: true, ...},
           db: {configured: true}, langfuse: {...}}
   Verifies the "is it demoable" boundary. No model, no DB.

2.  GET  /v1/conversations
    → 200 {items: [...], page: 1, page_size: 20, token: null}
   Verifies the envelope + the list contract. (May be an empty list on
   a fresh cluster; that's fine.)

3.  POST /v1/conversations
    → 201 {conversation_id: "c-…", created_at: "…"}
   Verifies the session primitive.
```

### Phase 2 — first grounded turn (NL → SQL)

```
4.  POST /v1/conversations/{id}/messages
     Body: {"text": "Which MCC codes have the highest fraud rate among
             those with at least 1,000 transactions?"}
    → 201 {message_id: "m-", run_id: "run-…", status: "running"}
   The command returns IMMEDIATELY. ADR-0011's split is verified here:
   the turn is durably created, but the LLM is still running.

5.  GET  /v1/runs/{run_id}/events     (SSE; expect these in order)
      run.start
      tool_call.start   {tool: "run_sql", args: {…}}
      tool_call.done    {tool, result_summary}
      message.delta     {delta}          (one or more)
      run.done          {message_id, duration_ms, tokens_in, tokens_out}
   The event set is asserted against the frozen list in
   api-contract.md. An unexpected name or order is a failure.

6.  GET  /v1/conversations/{id}/messages/{mid}
    → 200 {message_id, run_id, status: "success",
           grounding: {sql, explanation, assumptions,
                        tables_and_joins_used, flags},
           error: null,
           revisions: ["rev-1"]}
   The Gap A shape in action: the DTO is union-typed. On success,
   `grounding` is populated and `error` is null. `grounding` is a
   typed object, not a string (ADR-0006).
```

### Phase 3 — edit + re-run (the FSM owns the SQL)

```
7.  [as the FSM: I read the SQL, I see the agent wrote `txn_count > 1000`,
     but I actually want `amount > 5000 AND card_type = 'debit'`]

8.  POST /v1/conversations/{id}/messages/{mid}/rerun
     Body: {sql: "SELECT … WHERE amount > 5000 AND card_type = 'debit' …"}
    → 200 {message_id, revision_id: "rev-2",
           result: {columns: […], rows: [[…]],
                     row_cap: 100, truncated: false},
           flags: [...]}
   The Gap H closure in action: SYNCHRONOUS, not a run, not a stream.
   A rerun is a deterministic re-execute; there is nothing to stream.

9.  GET  /v1/conversations/{id}/messages/{mid}
    → 200 {…, revisions: ["rev-2", "rev-1"],
           grounding: {…}}   // the grounding here reflects rev-2 (the latest)
   The revisions list is now [2, 1], newest-first. The "live" revision
   is the one the FSM is looking at in the UI.
```

### Phase 4 — pin the insight (the bridge)

```
10. POST /v1/conversations/{id}/insights
      Body: {
        message_id: "m-",
        revision_id: "rev-2",                     // REQUIRED (Gap B)
        sql: "SELECT … WHERE amount > 5000 AND card_type = 'debit' …",
        explanation: "…(the pinned explanation, or null)"
      }
      → 201 {insight_id: "ins-…", …}
    The Gap B closure in action: the pin references the *exact revision*
    and carries the *exact SQL* the FSM saw. If a future rerun produces
    rev-3 and the FSM then pins, the insight stores rev-2 (the one the
    FSM chose) and rev-3 stays in the message's revisions list,
    unpinned. No silent swap.

11. GET  /v1/conversations/{id}/insights
        → 200 envelope of insight cards

12. GET  /v1/insights/{id}
        → 200 {insight_id, source_message_id, revision_id,
               sql, explanation?, headline_metric, …}
```

### Phase 5 — draft + backtest

```
13. POST /v1/insights/{id}/draft-rule
        → 201 {rule_id: "r-…", draft_where: "…",
                 rationale: "…", assumptions: ["…"]}
      The structural "a rule can only originate from a pinned insight"
      (spec principle 5) is verified here: the draft-rule route only
      exists under `/insights/{id}`, not under `/messages/{id}` or
      `/conversations/{id}/rules`.

14. GET  /v1/rules/{id}
        → 200 {rule_id, source_insight_id, where_clause,
               status: "draft", created_by, …}

15. PATCH /v1/rules/{id}
         Body: {where_clause: "amount > 5000 AND card_type = 'debit'
                   AND mcc_code IN (…)" , title?: "..."}
         → 200 {rule_id, status: "draft", …}
      Edit-and-own on the rule (spec §7.1). The LLM is not in the loop;
      this is a direct FSM edit.

16. POST /v1/rules/{id}/backtest
        → 201 {the BacktestResult DTO — see below, Gap C}
      The FSM is the only one who fires this. ADR-0005 wall visible in
      the shape: the response is *deterministic* — every number was
      computed in core/backtest.py, none was produced by the LLM.

   The BacktestResult DTO as it comes back (Gap C closure):
      {
        backtest_id, rule_id, created_at, window,
        metrics: {precision, recall, false_positive_rate,
                  baseline_fraud_rate, lift},
        confusion_matrix: {tp, fp, fn, tn},
        coverage: {matched_count, total_rows, total_fraud, support},
        temporal_stability: {earlier_slice: {…}, later_slice: {…}},
        sample: {
          count: 5,
          columns: ["id", "amount", "mcc_code", "card_type", "..."],
          rows: [[...], [...], [...], [...], [...]]
        }
      }
      The `sample` block is the "eyeball the matches" case — the FSM
      inspects these 5 rows before approving, and the contract *promises*
      they are here. (The orphaned `compute_backtest` in the current
      `db.py:174` already computes `sample_matched_columns` +
      `sample_matched_rows`; the gap was that the shape wasn't
       in the contract.)

    [freeze-line negative check — the "WHERE edits are sealed after
     backtest" invariant, frozen in rule-lifecycle.md]
    16a. PATCH /v1/rules/{id}
          Body: {where_clause: "amount > 6000 AND card_type = 'debit'"}
          → 409 {error: {code: "RULE_ILLEGAL_TRANSITION",
                        message: "…WHERE is frozen after backtest…"}}
       The status is unchanged from backtested. The FSM's response to the
       409 is to draft a NEW rule from the same insight — the old rule and
       its backtest stay as the record of "this WHERE, this evidence".
       The 200 alternative (roll back to draft) is specifically what the
       frozen 409 blocks, and this step is the headless assertion that the
       block works.

17. GET  /v1/rules/{id}/backtests
        → 200 envelope of backtest history (this run is the first item)

18. GET  /v1/rules/{id}/backtests/{bid}
        → 200 {the same BacktestResult object}
```

### Phase 6 — approve → deploy → catalog

```
19. POST /v1/rules/{id}/approve
         Body: {rationale: "precision exceeds threshold;
                        FPR is acceptably low; the sample rows
                        are consistent with an expected fraud profile",
                 actor: "fsm-placeholder-1"}
         → 200 {rule_id, status: "approved",
                  approved_at, approved_by, rationale}

20. POST /v1/rules/{id}/deploy
         → 201 {deployment_id: "dep-…",
                  external_rule_id: "ext-…"/*the fake ID from the mock*/,
                  timestamp}
      The mock `core/rule_engine.py` (spec §9) is exercised: the real
      downstream is out of scope, but the *contract* for it is
      exercised. The `external_rule_id` being a *fake* one is correct —
      that's what the mock returns.

21. GET  /v1/rules/{id}/deployment
         → 200 {deployment_id, rule_id, status: "deployed",
                 external_rule_id, deployed_at, payload: {...}}

22. GET  /v1/rules?status=approved
         → 200 {items: [{rule_id, title, status, …}],
                 page, page_size, token}
      The catalog, cross-conversation. The envelope is asserted: a
      future catalog with 10k rules will page; the shape allows it
      today.

23. [later, when the rule misbehaves]
     POST /v1/rules/{id}/disable
       → 200 {rule_id, deployment_id, disabled_at}
```

### Phase 7 — the failure path (the thing you can't fake)

The walkthrough *should* be able to drive this; the *current* script
will skip it because it can't force the LLM to write bad SQL on
demand. The eval suite (spec §10) is the thing that *does* drive this
via a red-team fixture. The shape contract below is what the eval
suite asserts.

```
24. [model writes bad SQL — a red-team fixture, not this script]
    The stream emits:
      run.error {code: "SQL_REJECTED",
                  message: "…(the validator's reason)…",
                  details: {offending_sql: "…(the exact SQL)…",
                            location: {line, column}} }

25. GET /v1/conversations/{id}/messages/{mid}
      → 200 {
            message_id, run_id,
            status: "error",
            grounding: null,
            error: {code: "SQL_REJECTED", message: "…", details: {...}},
            revisions: ["rev-1"]     // rev-1 failed; no rev-2
          }
    The Gap A shape under failure: the response is still `200` (the
    message *exists*), `grounding` is null, `error` is populated.
    The client's one error path handles it (ADR-0011: the same
    `error` object as a 5xx response body).
```

## The script contract (P1 deliverable)

The future `backend/scripts/e2e_walktalk.py` is the headless
implementation of *exactly* the walk above. Its responsibilities:

1. Stand up a fresh conversation (or reuse a seeded one) — a known
   state to start from.
2. Drive the API in the order above, phase by phase.
3. For each step, assert the *shape* of the response (not the
   *content* — the eval suite does that).
4. On any assertion failure: print the step number, the URL, the
   request body, the response body, and the traceback. Exit
   non-zero.
5. Print a summary at the end: which steps passed, which failed,
   total wall-clock time.

The script is part of `make eval`, alongside the promptfoo and pytest
suites. The three share the fixtures but have distinct assertion
layers:

| suite | asserts |
|---|---|
| `make test` (pytest) | deterministic logic + the ADR-0005 wall + the SQL validator + the backtest arithmetic |
| `make eval` (promptfoo) | the LLM's *output*: NL→SQL accuracy, faithfulness, red-team |
| `make eval` (this script) | the *shape* of every API response, over the full FSM workflow |

## Live mode and interactive REPL (P2 addition, 2026-09-03)

The two gatekeepers above (`pytest -q` and the default walk) run the LLM and the
`reference` reader as **fakes**. Two additions prove the *live* path is not
silently disabled:

**`backend/scripts/e2e_walktalk.py --live`** — the **repeatable** live gate.

- Real Ollama (`qwen3.8:27b-128k`) via `settings.llm_api_base`; real
  `reference` reader. Same 22-step walk, same shape-only asserts; no value-
  strict metrics (the model's SQL is non-deterministic).
- **Self-evidencing**: after the step-6 agent turn it prints
  `tokens_in` / `tokens_out`, the tool calls it made, the SQL it wrote, and
  the explanation it produced.
- **Hard-fails** if `tokens_in == 0` **and** the fake's canned prose
  ("1,159,966 transactions in the dataset.") appears in the grounding — i.e.
  the script detects "no real model call happened" instead of accepting a
  "PASSED" that was never real.
- Run from `backend/`: `.venv/bin/python scripts/e2e_walktalk.py --live`
  (needs Ollama: `curl -s http://localhost:11434/api/tags`).

**`backend/scripts/agent_repl.py`** — the **interactive** watcher. Type any
question and see the real model's tool calls, SQL, token counts, and grounded
answer print as they land. No script, no asserts: the point is to *watch* it.
It polls the durable `GET /v1/conversations/{id}/messages/{mid}` row until the
run is terminal, then reads `/events` **once** from the replay buffer — polling
the streaming endpoint mid-run would hang (the live subscribe queue doesn't
wake a suspended `get()` in the worker thread). Run from `backend/`:
`.venv/bin/python scripts/agent_repl.py`.

These are complementary, not redundant: the `--live` walk runs one canonical
path every time and is the regression gate; the REPL catches the behaviours
the walk's fixed questions never exercise (novel phrasings, multi-table joins,
the refusal to oversell a test-data artifact). The live pass of 2026-09-03
surfaced one concrete defect (fixed): `profile_column` in
`app/agents/graph.py` was computing
`nulls = total - non_null_count` and mis-labeling that as the nulls of the
column, so every non-null column showed `nulls == total` (see P2 addendum).

## Coverage — what I did *not* walk (and why)

The "parallel" verbs I did not drive individually because they reuse
a confirmed shape:

- `POST /v1/rules/{id}/reject` — mirror of approve; state machine,
  not a new shape.
- `PATCH /v1/insights/{id}` — the same edit-and-own verb as
  `PATCH /v1/rules/{id}`, one step up the object graph.
- `DELETE /v1/{conversations,insights,rules}` — prod standards
  (ADR-0012) but not on the happy path; the cascades are already
  spec'd in the contract.
- `GET /v1/conversations/{id}/messages/{mid}/revisions` — the
  tuning-history read. The revision *mechanism* I did exercise via
  rerun; this is a separate read of the same rows.

I consider these covered by "reusing a confirmed shape." A P1 second
pass can add them as trivial `verify` steps — they don't need their
own walkthrough.

## The diagram

The sequence rendering of this walk is the Mermaid source at
`../diagrams/FSM-e2e-walktalk.mmd`. Mermaid source is itself diffable
text (unlike `.excalidraw` JSON), so there is no binary export to keep in
sync — render it with any Mermaid renderer (VS Code preview, or
`npx @mermaid-js/mermaid-cli`) to view it. 1:1 with this doc per
ADR-0010: the diagram is the rendered output of the decisions this doc
makes, and this doc is the source.
