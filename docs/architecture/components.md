# Internal components & call graph

**Status:** accepted (frozen with the 2026-09-02 P0 freeze, same pass as `api-contract.md`, `rule-lifecycle.md`, `data-model.md`, and `agent-loop.md`).

ADR-0005 gave us the *layers* and the rule that no LLM-reachable path can skip a deterministic gate. This doc draws the *call graph* — the pieces inside the boundary (see `context.md`), how they call each other, and where a request actually goes end-to-end. The layers are the invariant; the graph is one specific instantiation that must obey it.

The load-bearing distinction this doc keeps straight: **`services/` owns the HTTP/SSE boundary, `agents/` owns the loop, `core/` owns the determinism, `data/` owns the connections.** Nothing in the graph crosses that split in the wrong direction, and the `agents → core` edge is the only one that's load-bearing at that altitude (ADR-0005's running test is the proof it's never reversed).

## The pieces, and what owns what

| package | role | reaches the DB? | reaches the LLM? |
|---|---|---|---|
| `app/api/routers/` | thin HTTP: parses the request, calls `services/`, serializes the DTO, returns. **No logic, no core calls, no LLM.** | no | no |
| `app/services/` | orchestration + the SSE event emitter + budgets (recursion-limit is a config it passes; the wall-clock budget it `wait_for`s around `astream`). Owns the run lifecycle end-to-end: writes the `runs`/`messages` rows before the stream opens (Command/query split, ADR-0011), maps LangGraph stream output → the frozen event set, writes the final state (grounding or error), and owns the PostgresSaver construction (so the checkpointer's `app_rw` connection is opened **here**, not in the agent). | **yes** — `app_rw` (appstate) | no (it calls `agents/`, never the model directly) |
| `app/agents/` | the LangGraph `StateGraph` (ADR-0003), the two tools (in `app/agents/tools.py`), the `structured_output` terminal node (ADR-0006). | **only via `core/`** — the two tools are the door | **yes** — the only LLM component |
| `app/core/` | the deterministic gates: `sql_validator` (ADR-0002), `flags`, `backtest`, `rule_state`, `rule_engine` (the mock). Pure or read-only. | **yes** — `reference_readonly` (reference), via the pools `data/` owns | **no** |
| `app/data/` | the two Postgres connection pools (`app_rw` for appstate, `repository` objects per table in `data-model.md`). No business logic; `core/` and `services/` call it, it calls Postgres. | yes (it *is* the pool) | no |

Two properties this table encodes that the graph below just draws:

- **The agent has exactly one door to data**: `app/agents/tools.py → core/`. There is no `core`-free path out of `agents/`, and no `agents/` import inside `core/`. That is ADR-0005, and the `tests/test_architecture.py` AST check (P1 DoD #3) is the running test that keeps it true.
- **The LLM is one component.** `agents/` is the only package that imports LangGraph or the chat model. `services/` calls `agents/`'s compiled graph (`astream`), it does not *construct* the model — the model lives in `agents/` and the pool of app-level concerns (SSE, budgets, persistence) lives in `services/`. The reason is ADR-0004's whole point: the LLM should never have to *choose* to skip a gate, so the LLM is kept out of every layer that owns a gate.

## End-to-end: `POST /v1/conversations/{id}/messages` (the command) followed by `GET /v1/runs/{run_id}/events` (the view)

```
HTTP POST                       services/                      agents/                 core/           data/
────────                        ─────────                      ─────────               ─────          ─────
routers/messages.post
  → services.run.start()
      · write runs row(status=running) ──────────────────────────────────────────────────────────── data (app_rw)
      · write messages row(status=running)────────────────────────────────────────────────────── data (app_rw)
      · construct compiled graph w/ PostgresSaver(app_rw) ────▶  (services owns the checkpointer)
      · build RunnableConfig (thread_id=run_id, callbacks for Langfuse, recursion_limit)
      · emit run.start
      · astream(graph, config) ───────────────────────────────▶ model node
                                                                │ (no tool calls yet)
  ◀── SSE: run.start ─────────────────────────────────────────────
                                                                model node → tools.run_sql
                                                                  │
                                                                  │ tools.py calls core/sql_validator.validate_sql
                                                                  │─────────────────────────────────────────────────▶ (pure)
                                                                  │   core/sql_validator rejects → ValueError
                                                                  │   services/ maps to run.error (SQL_REJECTED) and
                                                                  │   writes runs.status='error' + messages.status='error'   data (app_rw)
                                                                  │   (graph aborted; no grounding row)
                                                                  │
                                                                  │ core: exec SELECT as reference_readonly
                                                                  │──────────────────────────────────────────────────▶ data (reference_readonly)
                                                                  │   core/flags.run(result)
                                                                  │   return {columns, rows, row_cap, truncated, flags}
  ◀── SSE: tool_call.start / tool_call.done (summary = row_cap/truncated/flags)
                                                                model node (sees the tool result)
                                                                → structured_output (deterministic)
                                                                   · assembles grounding (sql+flags from transcript;
                                                                     explanation/assumptions/tables from model's msg;
                                                                     validated against ADR-0006)
  ◀── SSE: message.delta (preview of explanation)  ·  insight.suggested (if the nudge fired)
      · write messages.grounding (the ADR-0006 object) ───────────────────────────────────────── data (app_rw)
      · write runs.status='success', finished_at
  ◀── SSE: run.done ─────────────────────────────────────────────────────────────────────
```

Every vertical line in that trace is a call that *may* be made; none of the ones the LLM never chose are in the `agents/` column, because the only LLM node is `model` and the gate calls are inside the `tools.run_sql` body, not in a node the model routed around (`agent-loop.md` for the why).

### The two paths the agent *doesn't* have

- **`agents/ → services/`** does not exist. `services/` calls `agents/`, never the reverse. The reason: `services/` owns the HTTP/SSE and appstate persistence; if the agent could reach back into it, the "the agent's only door to the world is `tools.py → core/`" property would have a second door (the app state), and ADR-0005's wall would be two doors, not one.
- **`agents/ → data/`** does not exist. The DB is reachable only via `core/` (reference) or `services/` (appstate). The agent has no pool of its own; the `reference_readonly` connection is opened *inside a `core/` function*, not in `agents/`. This is spec §11.1's "enforced at the permission layer, not just prompted against" — the agent can't open a write connection because it doesn't have the credential.

## The `core/` gate functions (the deterministic surface)

| function | called from | invariants it enforces |
|---|---|---|
| `core/sql_validator.validate_sql(sql)` | `agents/tools.py::run_sql`, before execution | single read-only SELECT over allow-listed tables (ADR-0002); otherwise reject |
| `core/flags.run(result)` | `agents/tools.py::run_sql`, after execution | deterministic sanity flags (empty result, ≈full-table, etc.); the same `flags` stored on the revision and on the grounding |
| `core/backtest.run(where_clause, window)` | `services/` (the `POST /rules/{id}/backtest` handler), **never** the agent | the metric set (spec §8) + the sample; writes exactly one `backtest_results` row (the `rule-lifecycle.md` invariant that the row is anchored to a specific `WHERE`) |
| `core/rule_state.transition(rule.status, verb)` | `services/`, each of the `approve`/`reject`/`deploy`/`disable` handlers | the 5-state machine + the freeze line (only `draft` may `PATCH where_clause`; only from `backtested` may `approve`/`reject`; only from `approved` may `deploy`); returns the new status or raises a `409`-mapped exception |
| `core/rule_engine.deploy_rule(payload)` / `.get_rule_status(id)` / `.disable_rule(id)` | `services/`'s `POST /rules/{id}/deploy` (and the `GET …/deployment`, `POST …/disable` handlers) | assembles the spec §9 payload from already-structured data (no LLM); returns the fake `external_rule_id`. The real engine replaces this function, its call sites do not change (spec §9) |

The reason `core/` is the *only* place these invariants live is ADR-0004/0005: a prompt or a routing decision that *hoped* the LLM wouldn't skip a backtest is a weaker guarantee than a function the LLM can't invoke. `core/` is LLM-free and *transport*-free — it has no idea whether it was called from a `POST` handler or from a LangGraph tool node, and that is the point (it stays testable as a pure function).

## The frontend, as the consumer of the above

ADR-0009 already owns **where** the frontend lives (`features/{chat,workspace,insights,catalog}/` + `components/ui/`) and **the rule** for where a new file lands. This doc does not re-derive that — it only names the seam each area has with the call graph above, so a P3 implementer knows exactly which HTTP/SSE endpoint each feature owns:

| feature folder | the seam it owns | the contract lines it drives |
|---|---|---|
| `features/chat/` | the command (POST a message) + the SSE stream (attach/reconnect by `Last-Event-ID`) + the composer state. Owns `useSse`/the stream lifecycle; the frozen event set is *its* event source, not a generic subscription. | `POST /v1/conversations/{id}/messages`, `GET /v1/runs/{run_id}`, `GET /v1/runs/{run_id}/events` |
| `features/workspace/` | the grounded result (the last run's `grounding` + the live `tool_call` event stream it came from) + edit-and-own (PATCH the SQL, `rerun`) + the `revisions` read. | `GET …/messages/{mid}`, `POST …/messages/{mid}/rerun`, `GET …/revisions` |
| `features/insights/` | the pin (POST, Gap B: the client proves the exact `revision_id` + `sql`) + the rail read + the push-expand metrics panel (a `BacktestResult` read, not a new verb). | `POST /v1/conversations/{id}/insights`, `GET …/insights`, `PATCH/DELETE /v1/insights/{id}`, the `BacktestResult` via `GET /v1/rules/{id}/backtests/{bid}` |
| `features/catalog/` | the rule lifecycle verbs (draft/backtest/approve/reject/deploy/disable) and the catalog listing. This is the only feature that drives *any* of the rule verbs, and the one that depends most directly on `rule-lifecycle.md`. **No other feature may call these endpoints** — the "a rule can only originate from a pinned insight" property is structural (`rules.source_insight_id FK → insights`), but the UI enforcing it is "only the catalog feature has the rule-verb buttons." | `POST /v1/rules/{id}/…` (the rule verbs), `GET /v1/rules?status=…`, the `BacktestResult` |

`components/ui/` (the shared primitives: Button, Badge, the results table, the stat-card) are consumed by every feature and by none of the *verbs* — they render, they forward events, they call nothing (ADR-0009's "does things vs. renders" rule, restated only to fix the seam).

## Cross-doc drift caught in this pass (fixed in the same pass)

- **P1 DoD #2** names the SSE events as `tool_call_start` / `message_delta` / `done` / `error`. The frozen contract (accepted, `api-contract.md`) uses **`tool_call.start` / `message.delta` / `run.done` / `run.error`** — dotted, with the `run.` prefix on the terminal events. The contract wins (it is accepted; P1 is a placeholder). P1 DoD #2 should be updated to the frozen names when the P1 content lands.
- **`main.py` routes** are `/api/*` today; the frozen contract is `/v1/*`. This is a P1 rename, not a P0 concern — flagging it so the P1 implementer does not treat the `/api/` prefix in the current code as the contract.

## What this doc is *not* deciding

- **The prompt, the model, the provider config** — `app/agents/` internals and `app/common/model.py`, not a call-graph concern.
- **The SSE transport** (FastAPI `StreamingResponse`? `sse-starlette`? raw `text/event-stream`?) — a `services/` implementation detail, P1.
- **The specific TanStack Query keys, Zustand stores, or Vite aliasing** — a P3 internals, ADR-0009 owns the "where it lives" and this doc owns only the "what it talks to."

## Dependencies

- ADR-0003 (the loop this graph is a projection of).
- ADR-0004 (one agent; the graph shows it is one).
- ADR-0005 (the `agents → core` wall the graph obeys; the `agents ↔ core` asymmetry the graph keeps honest).
- ADR-0006 (the `structured_output` node and the typed grounding it produces, which `services/` then persists).
- ADR-0007 (the split between the `reference_readonly` door (`core/`'s) and the `app_rw` door (`services/`/`data/`'s)); the checkpointer sits on the `app_rw` side because it *writes*.
- ADR-0008 (the two pools and the checkpoint tables are Alembic-owned `appstate` DDL; `data/`'s repos are the runtime face of that).
- `agent-loop.md` (the graph *is* the call-graph projection of that; this doc adds the `services/` boundary and the two "no door" properties).
- `rule-lifecycle.md` (the `core/rule_state` function is the enforcement of that machine; this doc names *where* it's called, not *what* it does).
- `data-model.md` (the tables `services/` and `core/` read/write; the two pools `data/` owns).
- `api-contract.md` (the frozen route + SSE event set this graph's `routers/` and `services/` produce; the Gap A/B/C/H closures that the graph's `messages`/`insights`/`rules` write paths exist to support).
- spec §6.1 (the high-level shape), §6.3 (the deterministic pipeline = the `core/` surface above), §9 (the `rule_engine` mock this doc slots into the verb handlers).
