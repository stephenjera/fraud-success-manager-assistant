# Fraud Insight & Rule Copilot — System Specification

**Status:** accepted (frozen in the 2026-09-02 P0 freeze).

**This file is the authoritative system spec** — the only one. The old
root-level `fraud-insight-copilot-spec.md` is removed (the spec lives here,
not mirrored). The ADRs in `decisions/` are the decision record this spec
was *driven by*; `architecture/` is the detail this spec cross-references.

**Reads alongside:** `architecture/api-contract.md` (routes, DTOs, SSE events,
error codes), `architecture/data-model.md` (tables, columns, phase gates),
`architecture/agent-loop.md` (StateGraph, state channels, checkpointing),
`architecture/components.md` (backend call graph + frontend seam),
`architecture/rule-lifecycle.md` (FSM + the freeze line),
`architecture/eval-design.md` (what runs where, in which phase),
`architecture/context.md` + `architecture/deploy.md` (system boundary + what
boots), `ux/wireframes.md` + `ux/wireframes.html` (what the FSM actually
clicks), `phases/00-roadmap.md` (how the whole thing gets built).

---

## 1. Purpose

Fraud analysts (Fraud Success Managers, FSMs) work a repeating loop:
**explore** transaction data to form a hypothesis about a fraud pattern,
**validate** that hypothesis against historical data, and — if it holds up —
**codify** it into a concrete, deployable detection rule with known
precision/recall. Today this loop is bottlenecked by SQL/BI proficiency and
by the manual, error-prone process of going from "I think I see a pattern"
to "here is a rule I can defend."

This specifies a prototype — the *Fraud Insight & Rule Copilot* — that uses
a single tool-using LLM agent, wrapped in a deterministic application-level
pipeline, to compress that loop. The FSM interacts in natural language; every
factual claim the assistant makes is grounded in an executed, visible SQL
query; any pattern the FSM chooses to pursue can be turned into a
backtested, auditable rule (a SQL `WHERE` clause over `transactions` plus
supporting metadata).

**This is a local prototype meant to demonstrate production-grade
architecture and design thinking, not a production system.** Every section
below is explicit about what's built vs. deliberately deferred, and why —
scope decisions are first-class content, not omissions to apologize for.

---

## 2. Scope

### In scope (v1)

- Natural-language data exploration over the fixed reference schema
  (`cards`, `fraud_labels`, `mcc_codes`, `transactions`, `users`).
- A single tool-using LLM agent (LangGraph *StateGraph*, ADR-0003 — the
  tool-calling loop, streaming, and checkpointing — **not** for multi-agent
  routing per ADR-0004) that converts NL questions into safe, executed SQL
  and reasons over results, including proposing candidate patterns/insights.
- A deterministic (non-LLM) pipeline around that agent, in a three-layer
  wall (ADR-0005): `core/` owns the gates, `agents/` owns the LLM, `services/`
  owns orchestration. The agent reaches the DB **only** through `tools.py` →
  `core/`; it cannot open a connection.
- **Postgres** (ADR-0001): one cluster, two schemas (`reference`,
  `appstate`), two roles (`reference_readonly` SELECT-only, `app_rw` DML) —
  ADR-0007. Alembic owns the DDL (ADR-0008); `scripts/seed_reference.py`
  owns the reference *data* (idempotent `TRUNCATE`+`COPY`, superuser).
- SQL validation via **sqlglot** (ADR-0002): parse to AST, Postgres dialect,
  accept only a single read-only `SELECT` over allow-listed tables/columns.
  Not regex. Dialect-aware by construction.
- Full rule lifecycle: hypothesis → pinned insight → rule draft
  (FSM-editable) → backtest → human approval/rejection → export to a
  mocked rule engine. The state machine is deterministic code in
  `core/rule_state.py`, not a prompt; the freeze line (edit the
  `where_clause` after a backtest = `409`) is in
  `architecture/rule-lifecycle.md`.
- The **API as a product** (ADR-0011): versioned routes (`/v1/`), a command/
  query SSE split (`POST /messages` durably creates the run; `GET
  /runs/{id}/events` is a *view* of the durable state, reconnectable by
  `Last-Event-ID`), list envelopes, and a stable typed error shape. Any
  client — the reference frontend, `curl`, a future service — runs the full
  lifecycle with no different code path.
- A three-pane chat + workspace web UI (chat / SQL-results / insights rail)
  + a separate Rule Catalog page. Layout and coverage in `ux/wireframes.md`;
  directory map in ADR-0009 (`features/{chat,workspace,insights,catalog}` +
  `components/ui/`).
- **Langfuse tracing, external to this repo** (ADR-0012 skip row;
  `architecture/deploy.md`): if the `LANGFUSE_*` env vars are unset the
  tracing path is a no-op. The app is fully demoable with Langfuse absent.
- An evaluation suite split across **pytest** (SQL validator,
  sanity flags, backtest math, the rule state machine, the mock rule-engine
  client, and the E2E pattern-recovery pipeline) and an **LLM-judging
  suite** (NL→SQL execution accuracy, explanation faithfulness,
  safety/redteam) — the latter *deferred* until a judge model is available
  (§10.1). Both locate in `backend/eval/`; phase-gated per
  `architecture/eval-design.md`.

### Out of scope (v1) — and why

- **Auth/RBAC.** Single-user local prototype; no user to authenticate.
  `created_by` / `approved_by` fields exist and are populated by a
  placeholder identity so the data model doesn't need a rewrite.
- **Column-level sensitive-data masking.** The reference dataset is public.
  Masking solves a data-governance problem this prototype doesn't have.
- **A real downstream rule engine.** The *contract* (spec §9) is specified
  precisely and implemented against an in-process mock; the engine itself
  is a future boundary, not a v1 component. (See `architecture/context.md`.)
- **CI pipeline.** `make lint` / `make test` / `make eval` are the
  deliverables, runnable by hand or wired into CI later without code
  changes. ADR-0012 skip row.
- **Real-time/streaming transaction scoring.** This tool operates on
  historical data for investigation and rule design, not live decisioning.
- **Schema-introspection generality.** The schema is fixed and small —
  introspected once at startup and injected in full into the agent's system
  prompt. No tool, no paging, no admin UI (at this scale).
- **Terraform / a real deployment target.** ADR-0008 consequences; the
  "repro on a fresh cloud host" capability has no customer in this project.
- **Multi-tenant postdeploy, WAF, rate-limit tiers.** ADR-0012 skip row.
- **Feedback-loop learning and drift monitoring.** The *contract* for
  drift comparison is in `§10.4`; the build is deferred, listed in §15.

---

## 3. Design principles (and how they mitigate GenAI risk)

1. **The model never invents data.** Every factual claim is backed by an
   executed, visible SQL query. Structured output (not prose) always
   accompanies a claim: the SQL, a plain-English explanation, stated
   assumptions, tables/joins used, and any automated sanity flags — the
   ADR-0006 typed object, validated in the graph's terminal node, not hoped
   for from the model.
2. **The model never executes unsafe SQL.** Generated SQL is **parsed**
   (sqlglot, ADR-0002) and rejected unless it is a single read-only `SELECT`
   against allow-listed tables/columns, executed via the
   `reference_readonly` **role** (ADR-0007), with a row cap and statement
   timeout — *regardless of what the model produced*. The role is the floor;
   the validator is defense-in-depth on top. This is the property that makes
   spec §11.1 a *structural fact*, not an aspiration (the old "enforced at
   the permission layer" line was aspirational under SQLite; it holds under
   Postgres by construction).
3. **Backtesting and evaluation are computation, not conversation.** Rule
   backtesting (precision/recall/FPR/coverage/lift) is deterministic SQL
   aggregation in `core/backtest.py`. It is never an LLM task — there is no
   reasoning step there to delegate, only arithmetic, and arithmetic should
   never be allowed to hallucinate. ADR-0005's wall makes "the LLM has no
   path into `backtest_results`" a running test, not a comment.
4. **The FSM owns approval, and owns correction.** No rule reaches
   `approved` or `deployed` without an explicit FSM action. The FSM can edit
   any agent-generated SQL or rule `WHERE` clause directly; an edit
   immediately becomes the new "live" state for that thread, not a
   suggestion competing with the model's original draft.
5. **Insights are the required bridge between exploring and drafting.** A
   rule draft can **only** originate from a pinned insight — enforced by the
   data model (`rules.originated_from_insight_id`, the NOT-NULL column) and
   by the API (Gap B: the pin DTO requires `revision_id` + `sql`, both
   client-provided). Not by prompting the model to "always draft from an
   insight."
6. **Untrusted data is data, never instructions.** Query results (including
   free-text columns like merchant descriptions) are passed to the agent as
   clearly delimited tool output. The system prompt states explicitly that
   cell content is data to analyze, never instructions to follow — and the
   eval suite (§10.1 safety/redteam) defends against it, not just a prompt
   line taken on faith.
7. **Every FSM decision is observable, every agent step is traceable.** Tool
   calls, prompts, and responses are traced to Langfuse for debugging and
   audit — but tracing is an *enhancement layer*, never a dependency. If
   Langfuse is off, the system still works, runs, and is demoable
   (`architecture/deploy.md`).

---

## 4. Why a single agent, not multi-agent (ADR-0004)

The first major architecture decision, worth stating plainly: the workflow
has three cognitive-sounding stages (explore, spot patterns, draft rules)
that invite reflexively splitting them into three specialist agents behind
a supervisor. Rejected:

- All three share the same schema, the same tools (`run_sql`,
  `profile_column`), and the same kind of reasoning ("call a tool, reason
  over structured output"). Multi-agent earns its complexity when subtasks
  need genuinely different context/expertise/models — false here.
- The one real safety property a supervisor could offer — "backtesting
  always happens before a rule is shown as validated" — is **better
  achieved deterministically in application code** than through agent
  coordination. A graph edge that's supposed to be non-optional is,
  underneath, a routing decision an LLM makes; application code that
  requires a backtest row to exist before a rule can transition to
  `backtested` cannot be talked out of it. That's the ADR-0005 wall.
- Multi-agent adds latency (handoff round-trips), cost (multiple model
  calls per turn), and debugging surface (a tree of traces instead of one
  trajectory) for no corresponding benefit.

So: **one tool-using agent** handles all NL reasoning (exploration, pattern
spotting, rule-rationale drafting all use the same `run_sql` /
`profile_column` tools — "find an anomaly" is just a question with an
aggregate query behind it, not a different kind of task). **Deterministic
pipeline code** handles everything safety-critical: SQL validation, sanity
flags, backtesting, state-machine transitions, deployment packaging.
LangGraph is the loop, but the loop is *ours* — a native `StateGraph`
(ADR-0003) with an explicit structured-output terminal node (ADR-0006), not
a factory-produced packaged agent.

---

## 5. Tech stack

| Layer | Technology | Notes |
|---|---|---|
| Backend framework | **FastAPI** | thin `routers/` + `services/` orchestration layer |
| Config | pydantic-settings | fail-fast validation at startup |
| Agent orchestration | **LangGraph `StateGraph`** (ADR-0003) | native graph; explicit model + tools + structured-output nodes (ADR-0006). Not `langchain.agents.create_agent` (ADR-0004). Not multi-agent (ADR-0004). |
| LLM integration | LangChain | provider-agnostic chat model interface |
| LLM provider (default) | **Ollama, local** | on-host, `LLM_API_BASE`; swappable via env config. Judge model (eval) is a *different* model than the agent model. |
| SQL validation | **sqlglot** (ADR-0002) | AST-based, Postgres dialect; single read-only `SELECT` over allow-listed tables/columns |
| Database | **Postgres** (ADR-0001, ADR-0007) | one cluster, 2 schemas (`reference` read-only, `appstate` DML), 2 roles (`reference_readonly`, `app_rw`) |
| DB migrations | **Alembic** (ADR-0008) | owns role DDL + appstate DDL; the single orderable path to the target schema |
| Data loading | `scripts/seed_reference.py` | idempotent `TRUNCATE`+`COPY`, runs as superuser (ADR-0008); the *only* path to `reference` data |
| Observability | **Langfuse (external)** | not in this repo or this compose; env-driven, no-op if unset (ADR-0012 skip row). |
| API versioning | **`/v1/`** (ADR-0011) | all routes versioned; the SSE command/query split is the load-bearing part |
| Frontend framework | React + TypeScript | `features/{chat,workspace,insights,catalog}` + `components/ui/` (ADR-0009) |
| Styling | Tailwind CSS v4 | |
| UI components | shadcn/ui | |
| Data flow (client) | hand-rolled fetch client (`frontend/src/lib/http.ts`) + React hooks | each feature owns its API client and hooks; a small working layer — no TanStack Query/Zustand dependency |
| Linting / typing | ruff + mypy | `make lint` |
| Eval — LLM judging | *deferred* (no judge model available) | NL→SQL accuracy, faithfulness, safety/redteam — designed in §10.1, not yet runnable (§15) |
| Eval — deterministic | pytest | sanity flags, backtest math, E2E pattern recovery, state machine (see §10) |
| Containerization | Docker Compose | root `docker-compose.yml`: `postgres` + `pgadmin` + `api` + `frontend` — all four run as containers (`make up`) |

---

## 6. System architecture

### 6.1 High-level shape

```
 ┌───────────────────────────┐        ┌─────────────────────────────────────────┐
 │      Frontend (SPA)         │  HTTP  │             FastAPI backend              │
 │  Chat | Workspace |         │◄──────►│  routers → services → (agents) → core   │
 │  Insights rail | Catalog    │  SSE   │                                         │
 └───────────────────────────┘        │  ┌──────────────────────────────────┐   │
                                       │  │  LangGraph StateGraph (ADR-0003) │   │
                                       │  │  model ⇄ tools → structured_out │   │
                                       │  │  (no checkpointer — run        │   │
                                       │  │   state lives in appstate)     │   │
                                       │  └──────────────────────────────────┘   │
                                       │                                         │
                                       │  ┌────────────────────────────────────┐ │
                                       │  │  core/  (deterministic, no LLM)    │ │
                                       │  │   validator (sqlglot, ADR-0002)    │ │
                                       │  │   flags                            │ │
                                       │  │   backtest (metrics math)          │ │
                                       │  │   rule_state (FSM)                 │ │
                                       │  │   rule_engine (mock client)        │ │
                                       │  └────────────────────────────────────┘ │
                                       │                                         │
                                       │  schema reflection (once, at startup)   │
                                       │  RuleEngineClient (in-process mock)     │
                                       └────────────────────────────────────────┘
                                                             │
                                                             ▼
          ┌──────────────────────────────────────────────────────────────────┐
          │         Postgres cluster (one) — ADR-0001 / ADR-0007            │
          │  ┌───────────────────────┐        ┌──────────────────────────┐  │
          │  │  schema: reference    │        │  schema: appstate         │  │
          │  │  cards, transactions, │        │  conversations, runs,     │  │
          │  │  users, fraud_labels, │        │  messages, revisions,     │  │
          │  │  mcc_codes            │        │  insights, rules,         │  │
          │  │                       │        │  backtest_results,        │  │
          │  │  role:                │        │  deployment_records,      │  │
          │  │  reference_readonly   │        │  (no checkpoint tables)   │  │
          │  │  (SELECT only)        │        │                           │  │
          │  │  data:                │        │  role: app_rw (DML)       │  │
          │  │  seed_reference.py    │        │  DDL: Alembic (ADR-0008)  │  │
          │  └───────────────────────┘        │  DDL: Alembic (ADR-0008)  │  │
          │                                   └──────────────────────────┘  │
          └──────────────────────────────────────────────────────────────────┘

          LLM  (Ollama on host, or provider via `LLM_API_BASE`)
          Langfuse  (external — not in this repo, no-op if unset)
```

Details: `architecture/context.md` (inside vs. outside the system),
`architecture/components.md` (the call graph and the seam),
`architecture/agent-loop.md` (the StateGraph nodes, state channels,
checkpointing), `architecture/data-model.md` (the tables and phase gates),
`architecture/deploy.md` (what boots, in what order).

### 6.2 The agent

**One LangGraph `StateGraph` tool-calling agent**, owning the conversation
loop for a given message: `model` ⇄ `tools` → `structured_output`. Three
state channels — `messages`, `grounding`, `error`. The `structured_output`
node is the ADR-0006 terminal node, an *explicit* graph node that assembles
the typed grounding object (reads the SQL and flags from the transcript,
validates the model's free-text fields against the schema) — not a prompt
hope. No LangGraph checkpointer: the graph is compiled bare (`g.compile()`),
and run state is persisted in `appstate` (`runs` + the SSE event log) by the
service layer — ADR-0016. Full detail in `architecture/agent-loop.md`.

**Tools available to the agent:**
- `run_sql(query)` — executes a SQL statement. Every call passes through
  `validate_sql` (sqlglot, ADR-0002) first and executes under the
  `reference_readonly` role (ADR-0007). Every result passes through the
  sanity-flag pipeline before being returned to the agent.
- `profile_column(table, column)` — returns distinct values (or top-N +
  cardinality if high-cardinality), min/max, null rate. Exists specifically
  to stop the model from guessing literal values for `WHERE` clauses — the
  silent failure mode where the query runs, returns zero or a wrong subset
  of rows, and looks fine to an FSM.

**Deliberately not a tool:** `get_schema`. The schema (5 tables) is
reflected once at startup and injected in full into the system prompt —
making it a tool would spend a round-trip for something static and small.
That's the ADR-0002/ADR-0003/ADR-0006/ADR-0005 stack, in one sentence:
the model only reaches the DB by emitting a tool call, the tools call
`core/`, and the gates in `core/` are the enforcement.

**Structured output (ADR-0006):** every assistant turn returns a typed
contract — `{sql, explanation, assumptions, tables_and_joins_used, flags}` —
with `flags` injected from `core/flags` (deterministic) and the `sql` read
from the transcript (a fact, not a model claim). The frontend renders
these fields directly; it never parses model prose. The SSE event set
around it (frozen, in `api-contract.md`) is `run.start`, `tool_call.start`,
`tool_call.done`, `message.delta`, `insight.suggested` (optional),
`run.done`, `run.error`, `run.timeout`.

### 6.3 Deterministic pipeline (non-LLM, non-bypassable)

| Step | Trigger | Where it lives (ADR-0005) |
|---|---|---|
| `validate_sql` | Every `run_sql` call, before execution | `core/sql_validator.py` (ADR-0002, sqlglot, Postgres dialect) |
| Sanity flags | Every query result, before returning to agent | `core/flags.py` (pure functions) |
| Backtest (precision/recall/FPR/coverage/lift/temporal-stability) | FSM fires `POST /v1/rules/{id}/backtest` | `core/backtest.py` (deterministic math, never LLM) |
| Rule state machine | Every FSM lifecycle verb | `core/rule_state.py` (deterministic; the `409` on illegal transitions) |
| Deployment payload assembly | FSM fires `POST /v1/rules/{id}/deploy` | `core/rule_engine.py` (mock client; no LLM) |
| Orchestration + SSE + durable state | Every HTTP call | `services/` (wires `agents` → `core` → `data`; enforces ordering) |

None of these are agent tools the model invokes — they are the enforcement.
The ADR-0005 wall (`agents → core` is the only dependency allowed between
them, and it is a *function* boundary, not a *graph* boundary) is enforced
by `tests/test_architecture.py` — a running AST check, so it survives
refactors that would otherwise quietly leak a direct DB call into the agent
or skip a validator. Spec-principle 3 is no longer aspirational by the time
P1 ships.

### 6.4 Persistence — one cluster, two schemas, two roles

- **`reference` schema** — the fixed reference dataset (five tables). Loaded
  once by `scripts/seed_reference.py` (superuser; idempotent `TRUNCATE`+`COPY`).
  The *only* role that touches it is `reference_readonly` (SELECT-only).
  The application **cannot write to it**: `INSERT`/`UPDATE`/`DELETE` on
  `reference.*` is a *permission error*, not a caught exception. This is
  the §11.1 "enforced at the permission layer" property, made structurally
  true by ADR-0007.
- **`appstate` schema** — the application's own state:
  `conversations`, `runs`, `messages`, `revisions`, `insights`, `rules`,
  `backtest_results`, `deployment_records`. No LangGraph checkpoint tables
  — the graph runs without a checkpointer (ADR-0016); run state is the
  `runs` row. Owned by `app_rw` (DML). Full read/write from the app; never written to by the
  agent (the agent has no path to `appstate` — that's the ADR-0005 wall made
  concrete: the agent reaches `reference` via `core/sql_validator.py` +
  `reference_readonly`, and the app reaches `appstate` via `services/`).
- **DDL**: Alembic owns it (ADR-0008). `alembic upgrade head` is the single,
  orderable, reviewable path to the target schema + role state on any fresh
  or existing cluster.
- **Data**: the seed script owns it (same ADR-0008). It is the *only* path
  that touches `reference` data — and it runs as a separate superuser, not
  as `reference_readonly`.

Tables, columns, FKs, JSONB sub-objects, and phase gates:
`architecture/data-model.md`. Two DBs sharing a cluster (rather than two
clusters, or two logical "prod/dev" Postgres instances) is the ADR-0007
topology call; the *load-bearing* property is that the write path and the
read path are *roles*, not *mode flags* — which is what SQLite's `?mode=ro`
couldn't deliver and is what made the Postgres swap (ADR-0001) worth it.

### 6.5 Streaming model — the command/query split

The chat `POST /v1/conversations/{id}/messages` is a **command**: it
dureably creates the message and starts the run, returns
`201 {message_id, run_id, status:"running"}` immediately. The **view** is
`GET /v1/runs/{run_id}/events` (SSE), reconnectable by `Last-Event-ID`.
A dropped or closed stream does not *lose* the answer — the answer was
stored by the command. Any client (browser, `curl`, a future service) can
attach to a run in flight, replay a finished one, or poll — same data, no
different code path. The full event set is in `api-contract.md`; the
durable state it streams *from* is the run row in `appstate`, not a copy.

This is the ADR-0011 consequence that makes "the API is the product" true:
the frontend is one *consumer* of the contract, and a `curl`-script or a
Python eval harness would consume the same endpoints. The transparency-of-
reasoning value-prop (spec §6.5 / principle 7) is a *consequence* of the
durable-state design, not a bolt-on.

---

## 7. Object model & workflow

**`Conversation` → `Message` → `Insight` → `Rule` → `BacktestResult` →
`DeploymentRecord`.**

1. **Explore** — FSM asks NL questions; agent runs SQL via its tools;
   results + structured explanation rendered in the workspace pane. FSM can
   edit the SQL directly and rerun — the edited query becomes the new
   "live" query for that thread (a `revision`, per
   `api-contract.md` Gap H), and subsequent NL turns are interpreted
   against it, not against the model's original draft.
2. **Pin** — FSM promotes a specific query + result to a persisted
   **Insight** (`POST /v1/conversations/{id}/insights`). The pin DTO is
   *Gap B*: `message_id` + `revision_id` (REQUIRED) + `sql` (REQUIRED) +
   `explanation` (optional). This is the "one source of truth per object"
   property — the *exact revision* the FSM intended is what the insight
   records, and a re-pin after more reruns does not silently swap the SQL.
3. **Draft a rule** — from a **pinned** insight, `POST
   /v1/insights/{id}/draft-rule` fires the agent (rationale + assumptions)
   to propose a `WHERE` clause. The FSM can edit the `where_clause` (and
   `title`) on the resulting rule *directly* before backtesting — same
   edit-and-own pattern as SQL.
4. **Backtest** — deterministic, FSM-triggered, never LLM-invoked. `POST
   /v1/rules/{id}/backtest` → `core/backtest.py` computes the full metric
   set (§8) and writes one `backtest_results` row.
5. **Approve / reject** — explicit FSM action, recorded with actor
   (placeholder identity; §2 auth note), rationale, timestamp. The state
   machine (`core/rule_state.py`) is the enforcer: `deploy` from `draft` is
   a `409 RULE_ILLEGAL_TRANSITION`, not a silent no-op.
6. **Deploy (mocked)** — only valid from `approved`; assembles the
   deployment payload (`core/rule_engine.py`, mock client) and returns the
   `DeploymentRecord` + fake external rule ID. `deployment_records` is the
   durable artifact of deployment — the *payload the mock received*, with
   the full provenance and the full latest `BacktestResult`.

**Rule state machine** (enforced in `core/rule_state.py`, `architecture/
rule-lifecycle.md`):

```
  draft ──► backtested ──► approved ──► deployed
                 │
                 └──────► rejected    (terminal)
```

`deploy` is the only path *out* of `approved`; `rejected` is terminal (no
coming back). The **freeze line** (a `PATCH where_clause` after a backtest
row exists → `409`) keeps the catalog unambiguous — the FSM is forced onto
the clean path (a new rule from the same insight) rather than a silent
`approved`→`draft` demotion while the `deployment_record` still points at
the old `WHERE`. `PATCH title` stays editable at every stage.

---

## 8. Backtest metrics (`BacktestResult`)

Computed deterministically against `transactions` joined to
`fraud_labels` within a configurable evaluation window. **No field in this
DTO is generated by the LLM.** ADR-0005's wall is visible: the FSM triggers
the backtest (a command), `core/backtest.py` computes it, and the LLM has
no path into it.

| Metric | What it answers |
|---|---|
| **Precision** | Of flagged transactions, what % are actually fraud |
| **Recall** | Of all fraud in the window, what % does the rule catch |
| **False-positive rate** | Of legitimate transactions, what % get wrongly flagged — the customer-friction cost |
| **Coverage / support** | Matched count, as raw count and as % of total volume — turns "statistically interesting" into "operationally relevant" |
| **Lift** | Fraud rate inside the matched set vs. baseline fraud rate — the "better than random" framing |
| **Temporal stability** | Precision/recall on an earlier vs. later time slice — the main defense against a rule overfit to sample noise; surfaced, not something the FSM has to think to check |

Also returned (`api-contract.md` Gap C, `sample`): a **capped sample of
matched rows** so the FSM can eyeball actual matches, not just trust
aggregates — the whole "I don't trust aggregates, show me the rows" case.
Every field in the DTO is a deterministic function of the seed data + the
`where_clause`.

Deliberately excluded: dollar-value-weighted metrics (fraud $ captured vs.
legitimate $ blocked). Not ruled out on principle — genuinely useful to a
Head of Fraud — but contingent on `transactions.amount` data quality, which
hasn't been verified. Add once confirmed, not before.

**The full DTO** (fields, `metrics`, `confusion_matrix`, `coverage`,
`temporal_stability`, `sample`) is in `api-contract.md` Gap C; the *table*
that stores it, `backtest_results`, is in `data-model.md`.

---

## 9. Rule engine contract (mocked)

Even with no real downstream system, the contract is specified precisely,
because *defining* "turn a pattern into a concrete, deployable rule" **is**
the deliverable for this phase.

**`RuleEngineClient`** — an abstract interface (`Protocol`/ABC) in
`core/rule_engine.py` (the ADR-0005 wall: the agent has *no* dependency on
it; only `services/` reaches it, from the FSM's `deploy` verb):
`deploy_rule(payload)`, `get_rule_status(rule_id)`, `disable_rule(rule_id)`.
v1 concrete implementation: an **in-process mock** — persists the payload,
returns a fake external ID, logs it. Swap for a real client later without
touching calling code. It is *inside the system boundary* even though it
isn't a service — `architecture/context.md` records the call.

**Deployment payload** (the `DeploymentRecord`, the durable artifact):
- Rule identity: `rule_id`, `version`, `where_clause`
- Human-readable description, category/tags
- Full provenance: `source_insight_id`, `created_by`, `approved_by`,
  `approved_at`
- The **full latest `BacktestResult`** (metrics + window) — the receiving
  system gets evidence the rule was validated, not just an assertion that it
  was. ADR-0011 consequence: the `rule.status` / `rule.last_changed_by` and
  the deployment row share one source of truth, so the catalog isn't left
  with three inconsistent statements about what's actually live.

---

## 10. Evaluation framework

Split deliberately by **shape of the thing being evaluated** — not every
category is an "LLM eval" problem, and forcing deterministic logic through
an LLM-judging tool would be its own shoe-horning. Detailed layout, repo
locations, and phase gates in `architecture/eval-design.md`.

### 10.1 LLM output judging — *deferred* (no judge model available yet)

*Design as of P4; there is no runnable config yet (no
`backend/eval/promptfoo/`), and §15 lists the deferral.* promptfoo
would be the runner; the design fits its actual model (input → provider
call → judged output) for three categories:

| Category | Golden data | Scoring |
|---|---|---|
| **NL→SQL execution accuracy** | `(question, reference_sql)` across: simple filters/aggregates, multi-table joins, aggregation-grain-ambiguous questions, fraud-label-involving questions | Custom assertion: execute **both** generated and reference SQL and compare **result sets** (not strings) |
| **Explanation faithfulness** | `(question, SQL, result)` → judged explanation | `llm-rubric`: is the explanation fully supported by the actual result set, with no unsupported claims and no missed caveats. Judge model **configured distinct from** the agent model |
| **Safety / refusal rate** | Adversarial set: non-`SELECT` requests, out-of-schema questions, ambiguous questions (expects a clarifying question, not a guess), prompt-injection-shaped content in fixture data | Expected-behavior match; promptfoo's redteam plugin set used directly |

**Provider under test:** the **real LLM endpoint** (real agent, real tool
calls, real seeded Postgres). A mock would evaluate a *stand-in*; this
evaluates the system.

### 10.2 pytest — deterministic logic & pipeline

| Category | What's tested | No LLM involved |
|---|---|---|
| **SQL validator** | Rejects non-`SELECT`, non-allow-listed tables/columns; accepts a valid read; enforces the row cap | ✔ |
| **Sanity flags** | Empty result, near-full-table match; crafted result sets | ✔ |
| **Backtest math** | precision/recall/FPR/support/lift/temporal-stability against a known confusion matrix | ✔ |
| **Rule state machine** | Illegal transitions return `409` (e.g. `deploy` from `draft`) | ✔ |
| **`RuleEngineClient` mock** | payload assembly, fake ID generation | ✔ |
| **E2E pattern recovery** (the *pipeline*, not components) | Inject a known synthetic fraud pattern into the seeded `reference` data (superuser, `TRUNCATE`+`DELETE` in teardown — the ADR-0008 seed-script pattern, *not* a fourth role), run an FSM-style prompt, pin the resulting insight, draft a rule, backtest, assert precision/recall against the injected pattern clears a threshold. Small n (2–3), sequential/stateful — which is exactly why this is pytest and **not** promptfoo. | ✔ |

### 10.3 Running the suite

`make eval` runs the **deterministic suite** (pytest, via
`backend/eval/harness.py`) against the running backend + the seeded
Postgres, prints a summary. The LLM-judged half (NL→SQL accuracy,
faithfulness, safety/redteam) is **deferred** until a judge model is
available — see §10.1 and §15; there is no promptfoo config yet (no
`backend/eval/promptfoo/`). Golden fixtures live under
`backend/eval/golden/`. Traces from a run are *also* emitted to Langfuse
if it's running (pure debug visibility) — but the suite's pass/fail and
its fixtures **never depend on Langfuse persisting anything.** If the
local Langfuse were wiped, `make eval` is unaffected.

### 10.4 Online evaluation (documented plan, *not* built in v1)

For a stakeholder conversation about ongoing effectiveness once real usage
exists:
- **Efficiency:** time from first message to a rule reaching `backtested`;
  turns/clarifications per successful rule.
- **Adoption/trust:** % of drafted rules reaching `approved` vs. `rejected`;
  % of conversations producing at least one pinned insight.
- **Quality drift:** for deployed rules, compare actual post-deployment
  precision/recall (once new labels arrive) against the backtest estimate
  that justified deployment.
- **Safety:** a lightweight "this was wrong" flag on any message in the UI,
  feeding a dashboard and (longer-term) the golden dataset.
- **Cost/latency:** p50/p95 per turn and per backtest, LLM cost per
  resolved rule — directly queryable from Langfuse traces when Langfuse is
  running.

---

## 11. Non-functional requirements

### 11.1 SQL safety — *structurally true* this time

- All agent-generated SQL **parsed** (sqlglot, ADR-0002) rather than
  regex-scanned, and rejected unless a single read-only `SELECT` (or, for
  rule drafts, a valid boolean `WHERE` expression) over allow-listed
  tables/columns (the ADR-0005 wall: `core/sql_validator.py`).
- Execution via the dedicated **`reference_readonly` role** (ADR-0007),
  enforced row cap and statement timeout, **regardless** of what the model
  requested. The role is the *floor*: an `INSERT`/`UPDATE`/`DROP` on
  `reference.*` is a permission **denied**, not a *caught exception*.
  (This is the "enforced at the permission layer, not just prompted
  against" property from principle 2, now delivered by construction — the
  thing SQLite's `?mode=ro` couldn't.)
- No DDL/DML under any circumstance, enforced at the permission layer —
  not just prompted against. ADR-0002 (sqlglot) is the *defense-in-depth*
  on top; the *role is the floor*. The two reinforce each other.
- The wall (ADR-0005): the `agents → core` edge is the only route to the
  DB, and the `core` functions (`sql_validator.py`) are the gate. `tests/
  test_architecture.py` is the running AST check (P0 DoD #5) that keeps it
  true, so a refactor that quietly adds `from app.core import` to
  `agents/` fails the test, not the production review.

### 11.2 Prompt-injection / untrusted-data defense

- Query results passed to the agent as **clearly delimited tool output**;
  the system prompt states explicitly that cell content (including
  free-text columns like `merchant`) is data to analyze, **never**
  instructions to follow.
- Covered by the **adversarial cases in the LLM-judged redteam suite**
  (designed in §10.1; *deferred* until a judge model is available — §15),
  not taken on faith from the prompt alone. If the model *does*
  get tricked, the eval suite catches it: the redteam fixtures inject
  injection-shaped content into fixture data and expect the model to treat
  it as data, not to act on it.

---

## 12. Langfuse — external, optional, no-op if absent

Langfuse is **not a container in this repo, not in this compose file, not
part of the deployment.** The app reads `LANGFUSE_BASE_URL` + the public +
secret keys from env; if they're unset, the entire tracing path is a no-op
and the app is **fully demoable with Langfuse absent**. That's the
`architecture/deploy.md` boundary, and the `architecture/context.md`
*"outside"* call: Langfuse is a separate process we could point at over
HTTP, but the system's correctness does not depend on it being up.

The `GET /v1/health/ready` response exposes `langfuse` as a health state —
the "is it demoable" probe for the tracing path specifically. The eval
suite (§10.3) can *also* emit traces to Langfuse if it's running, purely
for debug visibility into failures — but the suite's pass/fail and its
fixtures never depend on Langfuse persisting anything. If the local
Langfuse is wiped, `make eval` is unaffected.

---

## 13. Frontend UX

**Layout:** three-pane main view (chat / workspace / insights rail) + a
**separate** Rule Catalog page. Full frame coverage, the "Evaluate"
semantics open-decision, and the API mapping per element in
`ux/wireframes.md` + `ux/wireframes.html`.

- **Left — Chat panel:** conversation, streamed agent activity (the SSE
  events from `api-contract.md`: `tool_call.start/done` shown inline
  "querying database…", not hidden), message composer.
- **Center — SQL/Results workspace:** the current *live* query (model-
  generated or FSM-edited — always the latest revision), editable, a Run
  button, results as a table, structured explanation/assumptions/flags as
  cards alongside it — not raw JSON, not buried in chat prose. Revisions
  history visible.
- **Right — Insights rail:** pinned insight cards (collapsed: title +
  headline metric), always visible (not a tab — a core design principle is
  state stays visible). Clicking *Evaluate* push-expands the rail into a
  full metrics panel (narrowing the center pane, **not** overlaying it —
  the SQL that produced the insight stays in view alongside the metrics).
  *The rail's "Evaluate" semantics are still an open call — see
  `ux/wireframes.md`; the API blocks neither option.*
- **Rule Catalog — separate page** (not a tab): all rules across all
  conversations, filterable by status. "Browse everything, across
  sessions" is a different task shape than "the insight I'm working on
  right now," and folding them into one panel would conflate
  session-scoped and persistent-catalog concerns. Selecting a rule opens
  its detail (SQL, provenance, backtest history, approve/reject/deploy
  actions) without reopening the originating conversation.

**State management:** each feature owns its API calls (a small hand-rolled
fetch client, `frontend/src/lib/http.ts`) and holds the fetched state in
React hooks, refetching on relevant mutations (e.g. approving a rule
refreshes its detail and the catalog list). Transient UI state (active
tab, focused insight/rule ID, composer draft text) lives in component
state or a small app store — server data is never duplicated into it.

**Directory (ADR-0009):** `features/{chat,workspace,insights,catalog}/`
for the app slices, `components/ui/` for the primitives. Each `features/`
folder owns its API client + hooks + its own components + local state;
`components/ui/` stays stable. The two directories are a *rule of thumb*
for where a new file lands — they are **not** an enforcement boundary
(no test enforces them; Phase 3 shouldn't be blocked by structure).

---

## 14. Deliverables

1. Monorepo: `backend/` (FastAPI + LangGraph, layered
   `routers/` → `services/` → `agents/` → `core/` — ADR-0005, with
   `data/` as plumbing) + `frontend/` (React/TS, `features/` + `components/`)
   + `backend/eval/` (golden fixtures + `harness.py` deterministic runner
   + pytest) + **a single `docker-compose.yml` at the repo root**
   (Postgres + pgadmin + `api` + `frontend` — all four run as containers;
   the local-venv path in `architecture/deploy.md` is the
   fast-iteration alternative).
2. **This spec** — setup, architecture rationale, explicit deferred-items
   list (§2), how to run locally, how to run `make eval`.
3. `backend/alembic/` (migrations) + `backend/scripts/seed_reference.py`
   (the reference dataset, loaded as data not code — the ADR-0008 split).
4. Golden datasets under `backend/eval/golden/` + the deterministic
   pytest suite (`backend/eval/harness.py`), runnable via `make eval`
   (the LLM-judged config is deferred — §10.1/§15).
5. `Makefile` targets: `make lint`, `make test`, `make eval`, `make up`
   (docker compose), `make migrate` (alembic upgrade head), `make seed`
   (seed_reference.py), `make api` (uvicorn). Documented as the
   manually-run equivalent of a CI pipeline (CI is explicitly out of
   scope, ADR-0012).
6. `docs/architecture/` (all `accepted`, frozen in P0): `api-contract.md`,
   `data-model.md`, `agent-loop.md`, `components.md`, `rule-lifecycle.md`,
   `eval-design.md`, `context.md`, `deploy.md`, `e2e-walktalk.md` (+ its
   `.mmd` diagram in `diagrams/`).
7. `docs/ux/wireframes.html` (the four frames: 3-pane, rail-expanded,
   catalog, edit-and-own) + `wireframes.md` (the coverage check + the one
   open call).
8. `docs/decisions/0001-…-0016` — 0001–0012 `accepted` at the P0 freeze
   (done; ADR-0010's rule, recorded here as the reason the flip is a status
   line and not a rewrite), 0013–0016 `accepted` in the P3/P4 phases.
9. `tests/test_architecture.py` (the ADR-0005 wall AST check) — P0 DoD #5.

---

## 15. Explicitly-deferred (not built in v1, and why)

Recorded here so the deferrals are part of the design, not silent. The
ADR-0012 skip row is the *principle*; this list is the *concrete cases*.

- **Auth / RBAC** and multi-tenant isolation.
- **A real downstream rule-engine integration** (replacing the in-process
  mock `RuleEngineClient`).
- **Column-level sensitive-data masking** (only relevant once real PII is
  in scope; the reference dataset is public and the reference is a local
  dataset we don't have).
- **A real deployment target** (the ADR-0008 consequences line: the
  "repro on a fresh cloud host" capability has no customer in this
  project).
- **Post-deployment drift monitoring/alerting** (vs. the manual
  backtest-vs-actuals comparison in §10.4) — *documented* in §10.4, not
  built.
- **Feedback-loop learning** (using FSM approve/reject/flag actions to
  improve prompts or expand the golden dataset over time) — ADR-0012 skip
  row.
- **A CI pipeline** (ADR-0012 skip row: `make lint/test/eval` are the
  manually-run equivalent; CI-ready in shape but no pipeline configured).
- **WAF / rate-limit tiers** (ADR-0012 skip row).
- **The LLM-judged eval suite** (NL→SQL accuracy, faithfulness,
  safety/redteam — designed in §10.1, promptfoo-shaped) — *deferred*
  until a judge model is available; `make eval` runs the deterministic
  pytest suite in the meantime.
- **Dollar-value-weighted backtest metrics** (contingent on
  `transactions.amount` data quality — see §8).

---

## 16. How the decision record maps to this spec

| ADR | What it drives in this spec |
|---|---|
| ADR-0001 (Postgres, not SQLite) | §2 in-scope; §5 stack; §6.4 two schemas; §11.1 structural read-only floor |
| ADR-0002 (sqlglot over regex) | §3 principle 2; §6.2–6.3 gates; §11.1 the "parse" (not "regex-scan") |
| ADR-0003 (native LangGraph) | §4; §6.2 the `StateGraph`; §5 stack (not `create_agent`) |
| ADR-0004 (single agent) | §4; §6.2–6.3; §7 the FSM never fires the backtest directly |
| ADR-0005 (core/agents/services wall) | §6.1/6.3 the layers; §11.1 the running AST test |
| ADR-0006 (structured output) | §3 principle 1; §6.2 the terminal node; `api-contract.md` the SSE set |
| ADR-0007 (1 cluster, 2 schemas, 2 roles) | §6.4; §11.1 the read-only floor; `data-model.md` the tables |
| ADR-0008 (Alembic + seed) | §5 stack; §6.4 DDL vs. data split; `deploy.md` the boot order |
| ADR-0009 (features vs. components) | §13 the directory rule |
| ADR-0010 (decisions before diagrams) | `docs/diagrams/README.md`; the discipline in this doc |
| ADR-0011 (API as product; SSE split) | §6.5; §7 the lifecycle; `api-contract.md` the contract; `ux/wireframes.md` the coverage |
| ADR-0012 (aim for prod where cheap) | §2 out-of-scope rows; §12 the Langfuse boundary; §15 the deferred list |
| ADR-0013 (P1 scope is the explore loop) | §2 in-scope; rule lifecycle + PostgresSaver deferral to P2 |
| ADR-0014 (backtest universes and join basis) | §7 backtest semantics; §10.4 backtest-vs-actuals comparison |
| ADR-0015 (infra SQL init; Alembic owns appstate) | §6.4 DDL vs. data split; `deploy.md` boot order |
| ADR-0016 (MemorySaver is sufficient) | §6.2 no checkpointer; §6.4 no checkpoint tables; `api-contract.md` run state |

ADR-0010 and ADR-0012 are the *policy* ADRs — they're the reason this
document reads as a coherent pass rather than a patch pile.

---

## Appendix: where to look

| Question | File |
|---|---|
| "What's actually booting?" | `architecture/deploy.md` |
| "What's inside the system vs. outside?" | `architecture/context.md` |
| "What are the routes/DTOs/events/error codes?" | `architecture/api-contract.md` |
| "What are the tables and their columns?" | `architecture/data-model.md` |
| "What are the StateGraph nodes and state channels?" | `architecture/agent-loop.md` |
| "What's the call graph and the frontend seam?" | `architecture/components.md` |
| "What are the rule's lifecycle edges and the freeze line?" | `architecture/rule-lifecycle.md` |
| "What does the eval suite cover, and by phase?" | `architecture/eval-design.md` |
| "What does the FSM actually click?" | `ux/wireframes.html` + `ux/wireframes.md` |
| "How to run the whole thing end-to-end?" | `phases/00-roadmap.md`; `backend/README.md` |
