# The LangGraph `StateGraph`

**Status:** accepted (frozen with the 2026-09-02 P0 freeze, same pass as `api-contract.md`, `rule-lifecycle.md`, `data-model.md`).

ADR-0003 gave us the shape (an explicit `StateGraph`, not `create_agent`), ADR-0004 gave us the guarantee that the loop is **one** agent, ADR-0005 gave us the wall the loop must respect, ADR-0006 gave us the type it must exit with. This doc pins the specific nodes, edges, state channels, checkpoint policy, and the exact moment a tool call happens relative to model output — so `core/` and `services/` can be built against it without a second design pass.

The single rule the doc enforces: **the `agents → core` edge is the only wall, and it is a *function* boundary, not a *graph* one.** Everything that is safety-critical is a call *inside* a tool function, not a separate node the model was told about. The reason, stated once and used below: a model can skip a node it was told exists; it cannot skip a function it does not know is a function. That is the whole ADR-0005 property, and this graph is built so the property does not depend on the model's cooperation.

## The graph: 3 nodes, one loop

```
      ┌──────────┐   (tool calls in last msg)   ┌──────────┐
START ─▶  model  ──────────────────────────────▶   tools   ─┐
      └──────────┘                                         │
            ▲                                              │
            └────────────────── (no tool calls) ───────────┘
                        ┌───────────────────┐
                        │ structured_output │   (terminal)
                        └───────────────────┘
```

| node | what it is | LLM? |
|---|---|---|
| `model` | the chat model; emits the next message, which may or may not contain tool calls | **yes** — the only LLM node |
| `tools` | **one** node (LangGraph's `ToolNode`) that dispatches to the two tools and returns their results to the transcript | **no** |
| `structured_output` | a deterministic assembler: takes the model's final answer + the last `run_sql` result, produces the ADR-0006 typed grounding, writes it to the state slot | **no** |

**Edges, exactly two conditions:**
- `model → tools` **iff** the last message in `messages` carries one or more `tool_calls`.
- `model → structured_output` otherwise. `tools → model` always.

Nothing else routes. There is no branching on intent, no supervisor, no "maybe the model wants a backtest" edge — a backtest is FSM-triggered and never entered *from* the graph (ADR-0004/0005, `rule-lifecycle.md`). The loop terminates either at `structured_output` (success) or when a budget is exhausted (failure, handled in `services/`, below).

### Why the tools are one node

The model can only reach the database by emitting a tool call, and the only tools are `run_sql` and `profile_column`. Both live in `tools.py`, both call `core/`. The model has **no other path to data**: there is no direct connection, no `get_schema` round-trip for a second lookup. `tools` is a single node (not one per tool) because that is the single *door* — the ADR-0005 wall drawn as "the agent reaches the DB only via `tools.py` → `core/`," and a single node makes "the door" visible in the graph and the `agents → core` AST check (ADR-0005's running test) is what makes it a *running* test, not a comment.

### Why there is no `validate_sql` / `flags` node

The stub asked whether to make the gates explicit nodes "so ADR-0005's wall is visible in the graph itself." The answer is **no**, and it is load-bearing: `validate_sql` and the sanity `flags` run *inside the `run_sql` tool function* —

```
run_sql(sql)   # in tools.py
    → core/sql_validator.validate_sql(sql)      # refuse if not a single read-only SELECT
    → connect as reference_readonly, execute     # ADR-0007: writes here are a permission error
    → core/flags.run(result)                     # deterministic, never model-reported
    → return {columns, rows, row_cap, truncated, flags}
```

Making the gate a graph node would mean the model could be *told* "a validate node follows your tool call" and could, in principle, reason about it or be steered around it. A function the model never named cannot be reasoned around. The wall is the **function boundary**; `core/` is never imported from `agents/`, and the AST check enforces that. (If a future need ever wants the validation visible for *test* purposes, it is already visible: `core/sql_validator` and `core/flags` are the two functions, and they are unit-tested directly — that is where the "wall test" lives, not in the graph.)

## State

Three channels, and nothing else. Langfuse is *not* a channel — it is `config`.

| channel | type | who writes it | who reads it |
|---|---|---|---|
| `messages` | `list[AnyMessage]`, append-reducer | `model` appends its turn; `tools` appends the tool result; the user turn is seeded by `services/` before `invoke` | every node; **this is the transcript and the checkpoint's body** |
| `grounding` | the ADR-0006 typed object (`app/agents/output.py`) or `None` | `structured_output` (terminal) | `services/` persists it to `appstate.messages.grounding` |
| `error` | `{code, message, details?}` or `None` | `services/` sets it from an exception/timeout; `structured_output` does **not** clear it on a bad assemble | `services/` persists it to `appstate.messages.error` (Gap A) |

- The transcript (`messages`) is the source of truth for *what the agent did*: the last `run_sql` argument is the `sql` the grounding carries, the last tool result's `flags` are the `flags` it carries. The ADR-0006 fields the model writes (`explanation`, `assumptions`, `tables_and_joins_used`) come from the model's final message; the two fields that are *facts* (`sql`, `flags`) do not — they are read out of the transcript by `structured_output`.
- `run_id` is **not** a state channel. It is assigned by `services/` before `invoke` (the run row is written in `appstate.runs` before the stream opens — ADR-0011: the command stores the state before opening the view). The graph does not own or mutate it.
- **Langfuse** rides on `RunnableConfig.callbacks` + `config.metadata` (exactly as the current `agents.py:140` does), not a channel. A state channel that exists only to carry a callback handle would be a channel the graph has to thread but never reads — the `config` route is what LangChain/LangGraph give us for free.

## Checkpointing (frozen 2026-09-02: **PostgresSaver from P1**)

- **Backend:** `PostgresSaver`, **from P1** — decided 2026-09-02 (the in-flight-resume fork; the other option, `InMemorySaver` until P2, was rejected). A finished answer is durable either way because `services/` writes `grounding` to `appstate.messages` before the stream closes. In-flight resume *after a reload* is what PostgresSavers for: the checkpoint table outlives the process, so `attach to a run in flight` (ADR-0011's claim) is true, not aspirational.
- **Where:** the checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) live in **`appstate`, owned by `app_rw`**, created by the saver's `setup()` (Alembic-compatible — see `data-model.md`). They are **not** in `reference` — the agent's read path is `reference_readonly` (SELECT-only), and the saver *writes*, so it cannot coexist with that role.
- **Who owns the connection:** `services/`. It constructs the compiled graph with a PostgresSaver built on an `app_rw` pool and passes the `thread_id` (the `run_id`) with each `invoke`. The graph does not open its own connection to the checkpointer; `services/` is the one that does. This is consistent with ADR-0005 ("the DB is reachable only via `core/` (reference) or `services/` (appstate)") — the *reasoning state* of the agent is app-state, written by the app, which is exactly the split ADR-0007 drew.
- **Granularity:** a **node-boundary is the checkpoint boundary** (LangGraph's default: it snapshots at each superstep, which here is each node). There is no finer or coarser setting to choose at this altitude — the `messages` channel grows by one element per node, so the checkpoint after `model` and the one after `tools` are distinct snapshots, and replay between them is a property of those snapshots.
- **Lifetime:** a run's checkpoint is kept (it is the durable record of the trace) until its conversation is deleted. No TTL, no expiry — the reference dataset is static and the checkpoint is small relative to it; an expiry policy would be a cost with no customer. `DELETE /v1/conversations/{id}` cascades to delete the checkpoint rows for its runs (that cascade is a `services/`-owned DB op, not a graph op).

## Tool call, exactly where

The model does not "decide to call a tool" in a special slot. It emits a message that *either* has `tool_calls` *or* has an answer:

1. `services/` seeds `messages` with the user turn, `invoke`s the compiled graph with `thread_id = run_id`.
2. `model` runs → appends its message.
3. If that message has `tool_calls`, the `tools` node runs, each tool call executing the `core/` path above, and the results are appended. Loop to (2). The `recursion_limit = 25` (existing, `agents.py:31`) is the step budget: hitting it raises, `services/` catches, writes `runs.status='error'` + `messages.status='error'`, emits `run.error`.
4. If the message has no `tool_calls`, `structured_output` runs: reads the transcript, assembles the ADR-0006 object (validating the model's three free fields against the schema; injecting the two fact fields), writes `grounding`, and the graph ends. `services/` persists `grounding` → `messages.grounding`, sets `runs.status='success'`, emits `run.done`.

That ordering *is* the "when does a tool call happen relative to model output" answer: **not before, not after — the tool call is the model's next message.** There is no separate plan/act loop and no supervisor choosing tools; the condition for entering `tools` is a property of the model's output, and the wall is enforced inside the tool body, not at the graph edge.

## The terminal node (ADR-0006, concretely)

`structured_output` is **deterministic** — it makes no model call. Given a finished transcript it produces:

```
grounding = {
  sql:                    the last run_sql argument in `messages`      # fact, from the tool call
  explanation:            the model's final answer, field-validated    # model-written
  assumptions:            the model's final answer, field-validated    # model-written
  tables_and_joins_used:  the model's final answer, field-validated    # model-written
  flags:                  the `flags` field of the last run_sql result # fact, from core/flags
}
```

If the model's three free fields do not validate against the ADR-0006 schema, `structured_output` writes `error` (not `grounding`), the run is `error` with code `LLM_ERROR` (one of the frozen error codes, `api-contract.md`), and `services/` persists `messages.error`. That is the specific case ADR-0006 exists to remove from the "the UI parses prose" failure mode — and it is a *typed* validation, not a hopeful parse.

**Optional nudge:** `structured_output` may *additionally* emit an `insight_suggestion` (`{suggested: true, sql, headline_metric}`) — the material for the contract's non-blocking `insight.suggested` SSE event. It is a *nudge*, not a pin: the pin is the FSM's `POST /v1/insights` (Gap B, which requires the client to send the exact `revision_id` + `sql`). The model can suggest a turn is worth pinning, but it cannot pin it — that is spec principle 4/5 ("the FSM owns correction," "insights are the required bridge") held at the state level, not the prompt level.

## SSE: emitted by `services/`, not the graph

The graph is 100% HTTP-free, deliberately. `core/` is LLM-free *and* transport-free; `agents/` is LLM-only *and* transport-free; both stay testable without an SSE harness. The frozen event set (`run.start`, `tool_call.start/done`, `message.delta`, `insight.suggested`, `run.done`, `run.error`, `run.timeout`) is produced by `services/` projecting LangGraph's `stream_mode` output:

| SSE event (frozen) | source in `services/` |
|---|---|
| `run.start` | emitted once, by `services/`, immediately before `astream` (the run row already exists, so the event carries the real `run_id`) |
| `tool_call.start` / `tool_call.done` | LangGraph's per-tool stream events, mapped 1:1 (the `done` body carries a *summary* — `row_cap`/`truncated`/`flags` — not the full result, per spec §6.5 "summarized") |
| `message.delta` | the streaming preview of the final answer (the `explanation` being generated) — a *preview*; the authoritative `grounding` is what `structured_output` persisted |
| `insight.suggested` | present only if `structured_output` set the optional nudge |
| `run.done` / `run.error` / `run.timeout` | terminal exactly one; `run.timeout` fires when `services/`'s wall-clock budget (`wait_for` around `astream`) expires and it writes the run `timeout` |

The `run.timeout` path is why the budget lives in `services/`, not the graph: `services/` wraps `astream` in a wall-clock budget (in addition to the `recursion_limit` step budget), and on expiry it writes `runs.status='timeout'`, `messages.status='timeout'` (both are in the frozen `status` domain, `data-model.md`), and emits `run.timeout`. The graph itself has no notion of wall-clock; it has a step budget (a LangGraph property) and nothing else time-based.

**Resume** (the PostgresSaver payoff): because `services/` is what maps stream output, and the checkpointer is Postgres, a client that lost its stream reconnects with `Last-Event-ID` (contract §Runs) and `services/` re-emits from the checkpoint — the same durable state, one code path (ADR-0011). The `GET /v1/runs/{id}` + `GET …/messages/{mid}` path is the fallback that works even if the SSE reconnect is impossible (a full reload, not a resume).

## The one invariant, stated in one sentence

**The only model-to-database path is `model` → `tools` → `core/`, the gates are functions inside that path and not nodes the model can route around, the only LLM node is `model`, and the graph exits either through the deterministic `structured_output` node (success) or through a `services/`-written error/timeout — never through a third state the model was told about.**

That sentence is the contract between this graph, `core/` (the gates), `services/` (the run/state/SSE), and `data-model.md` (the `messages.grounding` / `messages.error` / `runs.status` it writes, and the checkpoint tables it occupies). The `agents → core` AST check is the running proof of the first clause; the ADR-0006 schema validation in `structured_output` is the running proof of the last one.

## What this doc is *not* deciding

- **The prompt.** The system prompt (currently `agents.py:33`) will change with the schema move (SQLite→Postgres wording, the "profile a column before a literal" guidance), but its *content* is an `agents/` implementation detail and its *boundary* (it does not, and cannot, replace the gates) is fixed by ADR-0005.
- **The model provider/wiring.** Ollama-by-default, swappable (spec §5) — that is `app/common/model.py` config, not this doc.
- **The deterministic math** in `core/backtest.py` / `core/flags` / `core/rule_engine.py` — `rule-lifecycle.md`, `data-model.md`, and ADR-0005 own those; this doc only *calls* them through the tool body and never *implements* them.

## Dependencies

- ADR-0003 (the graph is explicit, not `create_agent`; this doc is its concrete form).
- ADR-0004 (one agent; the multi-agent alternative it closes is the "supervisor could route around the gates" hole this design structurally prevents).
- ADR-0005 (the `agents → core` wall is the function boundary this graph is built around; the AST check is the running test).
- ADR-0006 (the `structured_output` terminal node is its concrete form; the ADR-0006 schema is validated there).
- ADR-0007 (the `reference_readonly` vs `app_rw` split is why the checkpointer lives in `appstate` and the agent's *read* path cannot touch it).
- ADR-0008 (the checkpoint tables are part of the `appstate` DDL Alembic owns, via the saver's `setup()`).
- `api-contract.md` (the frozen SSE event set + the Gap A message DTO this graph must produce + the frozen error codes `LLM_ERROR`/`RUN_TIMEOUT`/`SQL_REJECTED`).
- `data-model.md` (the `runs` / `messages` / `revisions` tables it writes, and the checkpoint tables it occupies).
- spec §6.2 (the two tools + the "no `get_schema` tool" decision), §6.3 (the deterministic pipeline the tool body is, not the graph's), §6.5 (the SSE the transparency value-prop depends on).
- `backend/app/agents.py` (the current shape being replaced: `create_agent` + a `get_schema` tool + in-memory conversations — all three of which this doc removes or supersedes, and the `recursion_limit = 25` + Langfuse-`config` pattern it keeps).
