# Fraud Insight & Rule Copilot — Product & Technical Specification

## 1. Purpose

Fraud analysts spend most of their time doing three things, in a loop: exploring
transaction data to form a hypothesis about a fraud pattern, validating that
hypothesis against historical data, and — if it holds up — turning it into a
concrete, deployable detection rule. Today this loop is bottlenecked by SQL/BI
proficiency and by the manual, error-prone process of going from "I think I see
a pattern" to "here is a rule with known precision/recall that I can ship."

This document specifies a **production-ready internal tool** — the *Fraud
Insight & Rule Copilot* — that uses an LLM-powered, tool-using multi-agent
system to compress that loop: analysts interact in natural language, the
system grounds every answer in real queries against the transaction database,
and any resulting pattern can be turned into a fully backtested, auditable
**rule** (a SQL `WHERE` clause over the `transactions` table plus supporting
metadata) ready to hand off to a downstream rule engine.

This is a specification for an AI coding agent to implement against. It is
intentionally decoupled from any single company's schema, infrastructure, or
downstream systems — it is designed to generalize to *any* relational
transaction dataset.

## 2. Scope

**In scope (v1):**
- Natural-language data exploration over an arbitrary, introspected relational
  schema (not hard-coded to one dataset).
- A hierarchical, supervisor-orchestrated multi-agent system (LangGraph) that
  turns NL questions into safe, executed SQL and turns validated patterns into
  candidate fraud rules.
- Full rule lifecycle: hypothesis → insight → draft rule → backtest → human
  review/approval → export to an external (mocked, but realistically
  specified) rule engine.
- A two-panel chat + workspace web UI.
- Full observability (LangGraph traces to self-hosted Langfuse).
- An offline evaluation suite (golden dataset + automated scoring) and a
  defined online evaluation/monitoring plan.
- Local-first, Docker Compose deployment, structured as a production codebase
  (clear API boundaries, typed, linted, tested, CI-ready).

**Explicitly out of scope (v1):**
- Authentication/authorization (SSO/OIDC, RBAC). The system is assumed to run
  behind existing network/access controls for now. The API and data model
  should not preclude adding auth later (e.g. `created_by` fields exist and
  are populated by a placeholder/service identity, but there is no login
  flow).
- Kubernetes/Helm. Docker Compose is the only deployment target.
- A real downstream rule engine integration. We define the integration
  contract precisely (Section 8) and implement it against a mock/stub
  client.
- Real-time/streaming transaction scoring. This tool operates on historical
  data for investigation and rule design, not live transaction decisioning.

## 3. Personas & Core Workflow

**Primary persona:** a fraud analyst (domain expert, not necessarily a SQL
expert) who is investigating a suspected fraud pattern and needs to:

1. **Explore** — ask questions of transaction data in natural language
   ("show me chargeback rate by MCC over the last 90 days", "which card BINs
   have the highest fraud rate for transactions over $500 with no 3DS?").
2. **Hypothesize** — narrow in on a specific anomalous pattern.
3. **Validate** — check that the pattern is real and material (not noise, not
   a handful of transactions, not already covered by an existing rule).
4. **Codify** — turn the pattern into a `WHERE` clause rule.
5. **Backtest** — see precision, recall, false-positive rate, and coverage of
   the candidate rule against historical labeled data.
6. **Review & approve** — a human always makes the final call. The system
   proposes; it never auto-deploys.
7. **Export/deploy** — send the approved rule, with full provenance and
   backtest evidence, to a downstream rule engine.

This maps directly to the system's core object model: **Conversation → Insight
→ Rule Draft → Backtest Result → Rule (approved) → Deployment Record.**

## 4. Design Principles (and how they mitigate GenAI risk)

1. **The model never invents data.** Every factual claim the assistant makes
   about transactions must be backed by an executed, auditable SQL query
   against the real database. No claim should be presented to the analyst
   without a "view query" affordance.
2. **The model never executes unsafe SQL.** Generated SQL is statically
   validated (parsed, not just regex-checked) to be a single read-only
   statement against an allow-listed schema, executed with a row cap, a
   timeout, and a dedicated read-only database role/connection.
3. **The model proposes, a human disposes.** No rule reaches "approved" or
   "deployed" status without an explicit analyst action. The system is a
   copilot, not an autonomous decision-maker.
4. **The database is untrusted input, not instructions.** Column values,
   merchant descriptions, user-entered fields, etc. returned from queries are
   treated as data to reason over, never as instructions to the agents
   (prompt-injection defense — see Section 9.4).
5. **Every agent step is observable and replayable.** Full traces (prompts,
   tool calls, tool results, tokens, latency, cost) are captured in Langfuse
   so any output can be audited and any regression can be debugged.
6. **The system generalizes across schemas.** Nothing is hard-coded to one
   dataset's table/column names. The system introspects whatever schema it is
   pointed at and grounds the agents in that introspected structure.

## 5. Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| Config | pydantic-settings |
| Agent orchestration | LangGraph (supervisor / hierarchical multi-agent pattern) |
| LLM integration | LangChain (provider-agnostic; model selection via env/config) |
| Observability / tracing | Langfuse (self-hosted) |
| Data access | SQLAlchemy Core + ORM (database-agnostic: SQLite for local/dev, Postgres for a production-like deployment) |
| Frontend framework | React + TypeScript |
| Styling | Tailwind CSS v4 |
| UI components | shadcn/ui |
| Server-state management | TanStack Query |
| Client-state management | Zustand |
| Linting / typing (Python) | ruff, mypy |
| Containerization | Docker, Docker Compose |

LLM provider must be swappable via configuration (e.g. `LLM_PROVIDER`,
`LLM_MODEL`, API key env vars) without code changes — implement against
LangChain's chat model interface so Anthropic, OpenAI, or others can be
selected at deploy time.

## 6. System Architecture

### 6.1 High-level shape

```
┌─────────────────────────────┐        ┌───────────────────────────────────────┐
│         Frontend (SPA)       │  HTTP  │              FastAPI backend           │
│  ── Chat panel (left)        │◄──────►│  routers → services → repositories     │
│  ── Workspace panel (right)  │  SSE   │                                        │
│     (results / rule /        │        │  ┌─────────────────────────────────┐  │
│      backtest / catalog)     │        │  │     LangGraph Supervisor Graph   │  │
└─────────────────────────────┘        │  │                                  │  │
                                         │  │        ┌───────────────┐        │  │
                                         │  │        │  Orchestrator │        │  │
                                         │  │        │  (Supervisor) │        │  │
                                         │  │        └───────┬───────┘        │  │
                                         │  │   invokes as tools, no agent-   │  │
                                         │  │   to-agent edges:                │  │
                                         │  │  ┌─────┬─────┬─────┬─────┬────┐ │  │
                                         │  │  │Data │Pat- │Rule │Back-│Deploy│ │
                                         │  │  │Expl.│tern │Draft│test │Pkg. │ │  │
                                         │  │  │Agent│Agent│Agent│Agent│Agent│ │  │
                                         │  │  └─────┴─────┴─────┴─────┴────┘ │  │
                                         │  └─────────────────────────────────┘  │
                                         │                                        │
                                         │  Schema Introspection Service          │
                                         │  Safe SQL Execution Service            │
                                         │  Rule / Insight / Backtest repositories│
                                         │  Rule Engine Client (mock, pluggable)  │
                                         └───────────────┬────────────────────────┘
                                                          │
                                          ┌───────────────┴───────────────┐
                                          │      Transaction Database      │
                                          │  (SQLite dev / Postgres prod)  │
                                          └─────────────────────────────────┘
                                          Langfuse (self-hosted, all traces)
```

### 6.2 Multi-agent design (LangGraph, supervisor pattern)

A **single Orchestrator (Supervisor) agent** owns the conversation. It is the
only node with authority to decide what happens next; specialist agents are
exposed to it **as tools it can invoke**, not as peers with edges to each
other. Specialist agents never call one another directly — every hand-off
goes back through the orchestrator, which decides the next step based on
conversation state. This keeps the system auditable (one place decides
control flow) and makes it easy to add/remove specialists later.

**Orchestrator (Supervisor) agent**
- Holds the conversation state (message history, active insight/rule draft
  IDs, current schema context).
- Has direct tools: `get_schema()`, `run_readonly_query(sql)` (for simple
  lookups it can do itself), and one tool per specialist agent below
  (`delegate_to_data_explorer`, `delegate_to_pattern_finder`,
  `delegate_to_rule_drafter`, `delegate_to_backtester`,
  `delegate_to_deployment_packager`).
- Responsible for deciding, turn by turn, whether the user's message needs
  exploration, pattern analysis, rule drafting, backtesting, or is just a
  clarifying question it can answer directly from context.
- Responsible for streaming intermediate step events to the frontend (see
  6.4) so the analyst sees what's happening, not just a final answer.

**Specialist agents (invoked only by the orchestrator):**

1. **Data Explorer Agent** — converts a natural-language question into a
   validated, executed, read-only SQL query against the introspected schema,
   and returns results plus a plain-language explanation. Tools:
   `generate_sql(nl_question, schema_context)`, `validate_sql(sql)`,
   `execute_readonly_sql(sql)`.
2. **Pattern / Insight Agent** — given prior query results (and, if useful,
   its own follow-up aggregate queries), identifies candidate anomalies:
   disproportionate fraud rates in a slice, outlier concentrations, rule-gap
   coverage (transactions flagged fraudulent but not covered by any existing
   rule), etc. Produces a structured **Insight** object (natural-language
   description + supporting SQL + supporting metrics) rather than free text.
3. **Rule Drafting Agent** — given an approved Insight, proposes one or more
   candidate `WHERE` clause rules against `transactions`, with a
   natural-language rationale, an estimated scope (row count matched), and an
   explicit list of assumptions/edge cases. Must re-use the same
   `validate_sql` tool as the Data Explorer to guarantee the WHERE clause is
   syntactically and semantically executable.
4. **Backtesting Agent** — takes a candidate rule's `WHERE` clause and runs it
   against historical labeled data (the fraud-label table/column, whatever
   it's named in the introspected schema) to compute precision, recall,
   false-positive rate, coverage/support, and lift vs. baseline fraud rate,
   over a configurable historical window. Returns a structured
   **BacktestResult**.
5. **Deployment Packager Agent** — once a human has approved a rule, assembles
   the full deployment payload (Section 8) and calls the `RuleEngineClient`.
   This agent does not decide *whether* to deploy — that decision is a human
   action recorded via the API — it only prepares and sends the payload
   after approval is recorded.

Each specialist agent is implemented as its own small LangGraph subgraph (or
a tightly scoped ReAct-style tool-calling loop) with its own system prompt,
its own restricted toolset, and its own Langfuse trace span, invoked as a
callable tool from the orchestrator graph. This bounded-tool-per-agent design
is itself a hallucination mitigation: an agent can only do what its tools
allow it to do.

### 6.3 Schema-agnostic operation (schema injection)

The system must not hard-code any table or column names. On startup (and on
a configurable refresh interval / manual refresh trigger), a **Schema
Introspection Service** uses SQLAlchemy reflection to build a structured
schema description: tables, columns, types, primary/foreign keys, and
(optionally, capped) a small sample of distinct values for low-cardinality
columns to help the model understand categorical fields (e.g. status enums).

This structured schema is:
- Cached (in-memory + persisted) and versioned; invalidated on manual refresh
  or detected DDL drift.
- Injected into agent context in two ways depending on schema size:
  - **Small/medium schemas:** full schema description in the system prompt.
  - **Large/wide schemas:** a `get_schema(table_name=None)` tool the agent can
    call to page through tables/columns on demand (schema-as-tool /
    retrieval, to avoid context bloat and to scale to real production
    databases with hundreds of tables).
- The system must also let an analyst/admin optionally annotate the schema
  (e.g. "this column is a foreign key to X even though it's not declared as
  one", "this table is the fraud ground-truth label table") via a small
  config file or admin endpoint, since real production schemas are often
  under-specified. This annotation, if present, is merged into the injected
  schema context.

The provided reference dataset (`cards`, `fraud_labels`, `mcc_codes`,
`transactions`, `users`) should be used as the default local dev dataset and
as the basis for the golden evaluation set, but the implementation must not
assume these names anywhere in code.

### 6.4 Conversation & streaming model

- Each analyst conversation is a persisted `Conversation` with an ordered list
  of `Message`s.
- Assistant messages are **structured**, not raw text blobs: a message can
  carry zero or more typed **parts** — `text`, `sql_query` (query + row-limited
  result set + column metadata), `insight` (structured Insight), `rule_draft`
  (structured RuleDraft), `backtest_result` (structured BacktestResult),
  `chart_spec` (a declarative spec, not an image, so the frontend renders it).
  This is the API boundary contract (Section 7) — the frontend never parses
  LLM prose to figure out what to render.
- The chat endpoint streams **agent step events** over SSE (planning, tool
  call started, tool call finished with a summarized result, agent handoff,
  final message parts) so the workspace panel can update live as, e.g., a SQL
  query executes or a backtest runs — this is important because backtests may
  take several seconds and the analyst should see progress, not a spinner
  with no context.

## 7. API Design & Boundaries

**Principle:** the frontend talks only to the FastAPI backend, never directly
to the database or to any LLM provider. The backend never returns raw
LLM-formatted text as the sole representation of structured data — every
piece of structured content (query results, insights, rule drafts, backtest
metrics) is returned as a typed Pydantic schema so the frontend can render it
deterministically. Free-text is only used for the assistant's conversational
narration.

**Layering (backend):**
`routers/` (HTTP concerns only) → `services/` (business logic, orchestrates
LangGraph runs, enforces state transitions e.g. "cannot deploy a rule that
hasn't been approved") → `repositories/` (SQLAlchemy persistence, one per
aggregate: conversations, insights, rules, backtests, deployments) →
`agents/` (LangGraph graphs, isolated from FastAPI — testable headlessly).

**Indicative resource model / endpoints** (final naming left to the
implementer, but the resources and boundaries below must exist):

- `GET /api/schema` — current introspected schema (for a schema browser UI
  affordance) and `POST /api/schema/refresh`.
- `POST /api/conversations` / `GET /api/conversations/{id}` — conversation
  CRUD.
- `POST /api/conversations/{id}/messages` — send an analyst message; returns
  an SSE stream of agent step events terminating in the persisted assistant
  message with its structured parts.
- `GET /api/insights/{id}` — a persisted Insight (so it can be linked/shared
  and re-opened outside the chat that produced it).
- `POST /api/rules` (created from an insight) / `GET /api/rules` (catalog,
  filterable by status) / `GET /api/rules/{id}`.
- `POST /api/rules/{id}/backtest` — trigger (or re-trigger) a backtest run,
  returns a `BacktestResult`; long-running, should be a background task with
  status polling or SSE.
- `POST /api/rules/{id}/approve` / `POST /api/rules/{id}/reject` — explicit
  human decision, records actor + rationale + timestamp. (Actor is a
  placeholder identity in v1 since auth is out of scope, but the field must
  exist.)
- `POST /api/rules/{id}/deploy` — only valid from `approved` status; invokes
  the Deployment Packager Agent / `RuleEngineClient` and records a
  `DeploymentRecord`.
- `GET /api/rules/{id}/deployments` — deployment history for a rule.
- `GET /api/health`, `GET /api/health/ready` — liveness/readiness (DB
  reachable, LLM provider configured, Langfuse reachable).

**Rule status state machine** (enforced server-side, not just UI-side):
`draft → backtested → approved → deployed`, with `rejected` and
`superseded` as terminal/branch states. Illegal transitions (e.g. `deploy`
from `draft`) must return a 409/422, not silently succeed.

## 8. Rule Data Model & the External Rule Engine Contract

Even though no real downstream rule engine exists, the spec must define
exactly what would be sent to one, because that contract shapes the data
model end-to-end (this is the "concrete, deployable rule" requirement from
the source workflow).

**`RuleDraft` / `Rule`** (the same entity across its lifecycle, status field
changes):
- `id`, `version`
- `where_clause` (the SQL `WHERE` fragment — must always be validated as
  parseable and column-safe against the current schema before being stored)
- `natural_language_description`
- `source_insight_id` (provenance — always traceable back to the exploration
  that produced it)
- `status` (see state machine above)
- `created_by`, `created_at`, `approved_by`, `approved_at`
- `tags` / `category` (e.g. card-testing, BIN attack, chargeback pattern —
  free-form + a small controlled vocabulary)
- `confidence_notes` (assumptions/limitations the Rule Drafting Agent
  surfaced — must be shown to the reviewer, not hidden)

**`BacktestResult`** (one or more per rule, latest is authoritative for
display, all retained for audit):
- `rule_id`, `evaluated_at`, `evaluation_window_start/end`
- `matched_count` (rows matching the WHERE clause in the window)
- `true_positive_count`, `false_positive_count`, `true_negative_count`,
  `false_negative_count` (computed against the labeled ground truth in the
  window)
- `precision`, `recall`, `false_positive_rate`, `support` (matched / total),
  `lift` (matched fraud rate vs. baseline fraud rate in the window)
- `sample_matched_transactions` (a capped sample of matched rows for the
  analyst to eyeball, not just aggregate numbers)

**Deployment payload sent to `RuleEngineClient.deploy_rule(...)`** — this is
the answer to "what would we actually need to send a real system":
- Rule identity: `rule_id`, `version`, `where_clause`
- Human-readable description + category/tags
- Full provenance: `source_insight_id`, `created_by`, `approved_by`,
  `approved_at`
- Backtest evidence: the full latest `BacktestResult` (metrics + evaluation
  window), so the receiving system/audit trail has evidence the rule was
  validated, not just asserted
- Target mode: `shadow` (log-only, does not block) vs `active` — v1 should
  default every deployment to `shadow` and require an explicit separate
  confirmation to mark `active`, as a further safety gate
  a copilot has no business skipping.
- `review_date` / TTL — every deployed rule should carry a suggested
  re-review date so stale rules don't silently persist forever
- `rollback_reference` — a pointer back to the previous active rule version,
  if any, that this supersedes

**`RuleEngineClient`** must be defined as an abstract interface
(e.g. a `Protocol`/ABC with `deploy_rule`, `get_rule_status`,
`disable_rule`) with a **mock implementation** (persists the payload,
returns a fake external ID, logs it) as the v1 concrete implementation. This
guarantees a real integration can be dropped in later without touching
calling code.

## 9. Non-Functional Requirements

### 9.1 SQL safety
- All agent-generated SQL is parsed (not regex-matched) with a SQL parser
  (e.g. sqlglot) and rejected unless it is a single `SELECT` statement (or,
  for rules, a valid boolean expression usable in a `WHERE` clause) touching
  only tables/columns present in the introspected schema.
- Execution always happens through a dedicated read-only DB role/connection,
  with an enforced row cap and statement timeout, regardless of what the
  model asked for.
- No agent tool may execute DDL/DML under any circumstance — this must be
  enforced at the connection/permission layer, not just prompted against.

### 9.2 Data sensitivity
- Fields that are clearly sensitive by convention (PANs/card numbers, full
  DOB, national ID numbers, precise addresses) must be excluded from what's
  ever returned to the LLM or rendered in the UI by default — a
  configurable column-level "sensitive" flag (settable via the schema
  annotation mechanism in 6.3) that the Safe SQL Execution Service enforces
  by rejecting or masking `SELECT`s of flagged columns.

### 9.3 Testing & quality gates
- Python: `ruff` (lint + format) and `mypy` (strict-ish) run in CI on every
  PR; failing either blocks merge.
- Unit tests for: schema introspection, SQL validator, each repository, rule
  state-machine transitions, `RuleEngineClient` mock.
- Integration tests for: each agent's tool-calling behavior against a
  seeded SQLite test database, the chat endpoint's SSE contract, the full
  draft→backtest→approve→deploy happy path.
- Frontend: type-checked (TS strict), component tests for the two-panel
  layout and structured message rendering.

### 9.4 Prompt-injection / untrusted-data defense
- Query results returned from the database are passed to agents as
  structured tool outputs, clearly delimited from instructions, and agents'
  system prompts explicitly state that tool output content (including
  free-text columns like merchant descriptions or user-entered fields) is
  data to analyze, never instructions to follow.
- The Pattern/Insight and Rule Drafting agents must not be able to trigger
  further tool calls purely on the basis of content *inside* a data cell
  (e.g. a merchant name containing "ignore previous instructions") — this
  should be covered by adversarial cases in the eval suite (Section 10).

### 9.5 Deployment
- `docker-compose.yml` bringing up: backend, frontend, Postgres (for a
  production-like local run), self-hosted Langfuse (+ its own Postgres/
  ClickHouse per Langfuse's own compose requirements), and a seed step that
  loads the reference dataset into SQLite (dev mode) or Postgres (prod-like
  mode) — both must be one-command reproducible.
- All secrets/config via environment variables, validated at startup via
  pydantic-settings (fail fast on missing/invalid config, not at first
  request).

## 10. Evaluation Framework

### 10.1 Offline evaluation (pre-release / CI gate)

A **golden dataset** of realistic analyst tasks against the reference
dataset, each with:
- The natural-language input.
- An expected SQL query (or an equivalence check — see below) for
  exploration tasks.
- Expected structured outcome for rule-drafting tasks (e.g. "should identify
  that MCC X has anomalous fraud rate" without necessarily requiring an
  exact-match SQL string).
- A set of **adversarial/negative cases**: ambiguous questions the system
  should ask for clarification on rather than guess; prompt-injection
  attempts embedded in expected tool outputs; requests that would require
  non-read-only SQL (should be refused); questions outside the schema
  (should say so, not hallucinate a column).

Scoring approach:
- **Execution accuracy**, not string match — run both the generated SQL and
  the reference SQL and compare result sets, since multiple SQL strings can
  be semantically equivalent.
- **SQL validity rate** — % of generated SQL that passes the static
  validator and executes without error.
- **LLM-as-judge** scoring for: whether the assistant's natural-language
  explanation accurately reflects the query results (faithfulness check —
  the concrete anti-hallucination metric), and whether a drafted rule's
  rationale is consistent with its backtest evidence.
- **Rule quality metrics** on a held-out slice of labeled data: precision/
  recall/FPR of rules the system proposes for known-injected synthetic fraud
  patterns, to verify the system can actually find patterns it's meant to
  find.
- **Refusal/safety rate** — % of unsafe/out-of-scope/adversarial cases
  correctly refused or escalated to a clarifying question, not silently
  executed.

This suite should run automatically (via a `make eval` / CI job) against
Langfuse's dataset/evaluation features so runs are tracked over time and
regressions are visible per model/prompt version.

### 10.2 Online evaluation (post-release, ongoing)

Metrics to track once analysts are using the tool, to prove effectiveness to
a stakeholder:

- **Efficiency:** median time from first message in a conversation to a
  rule reaching `backtested` status (the core "time-to-rule" metric); number
  of analyst turns/clarifications needed per successful rule.
- **Adoption/trust:** % of AI-drafted rules that reach `approved` status vs.
  `rejected`; % of conversations that produce at least one persisted
  insight or rule (vs. abandoned exploration).
- **Quality in production:** for deployed rules, compare their *actual*
  post-deployment precision/recall (once new labels arrive) against the
  backtest estimate that justified deployment — large drift here is a
  signal the backtesting methodology or the underlying data drifted and
  needs attention.
- **Safety:** rate of analyst-reported incorrect/misleading answers (a
  lightweight in-UI "this was wrong" flag on any message, feeding both a
  dashboard and, longer-term, the golden dataset for regression coverage).
- **Cost/latency:** p50/p95 latency per conversation turn and per backtest
  run, and LLM cost per resolved rule — both trackable directly from
  Langfuse traces.

## 11. Frontend UX

**Layout:** two-panel single page.
- **Left — Chat panel:** the conversation, streamed agent activity (a
  lightweight "agent is querying the database…" / "backtesting rule…" trace
  shown inline, not hidden), and the message input.
- **Right — Workspace panel:** contextual, driven by what the conversation is
  currently producing — a tabbed/stateful area showing: query result tables
  and charts during exploration; the current rule draft (editable
  `WHERE` clause with live re-validation) once one exists; backtest results
  (metrics + sample matched transactions) once a backtest has run; and a
  persistent **Rule Catalog** view (all rules, filterable by status) reachable
  independent of any single conversation, since analysts need to browse and
  revisit rules across sessions.
- Selecting a rule from the catalog, or clicking a rule/insight referenced in
  chat, opens it in the right-hand workspace panel without losing the chat
  on the left — the two panels are independently navigable but linked by
  shared client state (Zustand) for "what's currently focused."
- TanStack Query owns all server-state (conversations, messages, rules,
  backtests, schema) with query invalidation on relevant mutations (e.g.
  approving a rule invalidates the rule detail and catalog list queries).
  Zustand owns transient UI state only (active panel/tab, focused
  rule/insight ID, composer draft text) — server data should never be
  duplicated into Zustand.

## 12. Deliverables

1. Monorepo with `backend/` (FastAPI + LangGraph app) and `frontend/`
   (React/TS app), plus root-level `docker-compose.yml`.
2. `README.md` covering setup, architecture rationale, how to run locally,
   how to run the eval suite, and explicitly listing any deferred/stretch
   items.
3. Seed script loading the reference dataset (`cards`, `fraud_labels`,
   `mcc_codes`, `transactions`, `users`) for local dev/demo.
4. Golden evaluation dataset + eval runner (Section 10.1) with results
   summarized in CI output.
5. CI pipeline (lint, type-check, unit+integration tests, eval-suite gate)
   defined for GitHub Actions (or equivalent), config-driven so it can run
   locally too.

## 13. Explicit Open Questions for Future Phases

These are intentionally deferred, not overlooked — call them out in the
README rather than silently building them:
- Auth/RBAC and multi-tenant isolation.
- Real downstream rule-engine integration (replacing the mock
  `RuleEngineClient`).
- Post-deployment automated drift monitoring/alerting (vs. the manual
  "compare backtest to actuals" check described in 10.2).
- Feedback-loop learning (using analyst approve/reject/flag actions to
  improve prompts or fine-tune retrieval over time).
