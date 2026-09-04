# Data model & the two roles

**Status:** accepted (frozen with the 2026-09-02 P0 freeze, same pass as `api-contract.md` and `rule-lifecycle.md`).

ADR-0007 gave us the topology — one Postgres cluster, two schemas (`reference`, `appstate`), two roles. ADR-0008 gave us the owner of the DDL — Alembic owns the `appstate` tables; `scripts/seed_reference.py` owns the *data* in `reference` **and the SELECT grant** on it (ADR-0015: role and schema DDL moved to `db-init/*.sql`, ran as a separate path, superseding ADR-0008's "Alembic owns roles/schemas" clause). This doc is the **content**: the tables, the real columns, the relationships, and the phase gates.

The one cross-cutting rule the whole doc enforces: **every row the frozen API returns, and every field of every DTO, is stored. Nothing the API returns is computed on demand *except* where the source is provably re-derivable from the fixed reference dataset** (and that case is named where it happens). If a field appears in `api-contract.md`, it has a column or a JSONB here.

## `reference` schema (read-only)

| table | role |
|---|---|
| `cards` | reference data |
| `fraud_labels` | reference data — the ground truth `is_fraud` labels |
| `mcc_codes` | reference data |
| `transactions` | reference data |
| `users` | reference data |

We do **not** define these columns here. They are external, fixed, loaded by `scripts/seed_reference.py` (idempotent `TRUNCATE` + `COPY`, ADR-0008), and only ever touched by the `reference_readonly` role (ADR-0007, `SELECT` only). `reference` is *data, not code* — its shape is whatever the seed says, and the agent reads it only through the `run_sql` tool.

Two facts about `reference` *are* ours, because the P2 backtest and the P1 validator depend on them:

- **The join** `fraud_labels.transaction_id = transactions.id` (ground truth ↔ the row it labels). Documented in `db.py:6`; the P2 `core/backtest.py` ports this exact join. If the real seed schema differs, that is the one line to find and change, not a refactor.
- **The label column** `fraud_labels.is_fraud` — the `COALESCE(SUM(fl.is_fraud))` in the backtest math (`db.py:194`) assumes a boolean-ish `is_fraud` per labeled transaction. `core/backtest.py` inherits this.

`appstate` never writes to these and these never write to `appstate`. The two schemas share a cluster, not a connection — that is the ADR-0007 boundary, and the `reference_readonly` role is the floor that makes `INSERT`/`UPDATE` on `reference` a permission error, not an exception.

## `appstate` schema (read-write, `app_rw` role)

Eight tables, all owned by `app_rw`, all versioned by Alembic. (ADR-0016: the agent's LangGraph checkpointer is in-memory (`MemorySaver`), so no checkpoint tables exist here. The `langgraph-checkpoint-postgres` dependency remains in `pyproject.toml` if a future deployment needs Postgres-backed checkpointing, but is not wired.) Primary keys are `uuid` (`gen_random_uuid()`); the ids the API exposes (`m1`, `r-…`) are the string form of these uuids. Statuses are `TEXT` with a `CHECK` constraint (not Postgres `ENUM` types — adding a value later is a one-line data change, not an `ALTER TYPE` migration). Structured sub-objects are `JSONB`, because nothing in the API filters *into* them (there is no `?precision=0.9` query), so there is no query pressure to denormalize them into columns — and the DTO 1:1-maps onto the column.

### `conversations`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | |
| `created_at` | `timestamptz` | |
| `last_active` | `timestamptz` | returned by `GET /v1/conversations` |

- No `title` — the contract's conversation objects carry no title, and the FSM names nothing. (A title column now would be a column the API never returns; ponytail says no.)
- `last_active` is a real column (cheap to maintain on each message insert); it is not derived.
- The contract's `message_count` is **computed** (`COUNT` of `messages` on read), not stored — a join the sidebar query does, so no redundant counter to keep in sync.

### `runs`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | the `run_id` the API exposes |
| `conversation_id` | `uuid` FK → `conversations` | `ON DELETE CASCADE` |
| `message_id` | `uuid` FK → `messages` | a run is one agent turn; 1:1 with the message it is the run *for* |
| `status` | `TEXT` | `CHECK IN ('running','success','error','timeout')` |
| `created_at` | `timestamptz` | |
| `finished_at` | `timestamptz` NULL | set when a terminal `run.*` event fires |

- This is **not** a duplicate of the agent's state. The trajectory (tool calls, intermediate messages, node checkpoints) lives in the **LangGraph checkpointer** (ADR-0003); this row is only the *small, readable identity + status object* that `GET /v1/runs/{id}` returns and that the SSE stream points at. ADR-0011's "the run is a first-class readable resource" needs a durable row to point at — it does not need a copy of the checkpoint.

### `messages`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | the `message_id` |
| `conversation_id` | `uuid` FK → `conversations` | `CASCADE` |
| `run_id` | `uuid` FK → `runs` | the run this message is the answer to |
| `status` | `TEXT` | `CHECK IN ('success','error','timeout')` **plus** the initial `'running'` at insert (Gap A: the union, the one thing the body tells the story for) |
| `created_at` | `timestamptz` | |
| `grounding` | `JSONB` NULL | the ADR-0006 typed object: `{sql, explanation, assumptions, tables_and_joins_used, flags}` — null until the run succeeds (Gap A) |
| `error` | `JSONB` NULL | `{code, message, details?}` — null unless the run failed (Gap A) |

- **No result-rows column.** Decided 2026-09-02: the *durable fact* of a turn is the SQL + explanation + assumptions + flags (exactly the frozen `grounding` DTO, which carries no rows). Result rows are **re-fetched, not stored** — the reference dataset is fixed, so `rerun` (Gap H) re-derives them deterministically. If a P3 frontend wants a cold reload of a past turn's numbers it calls `rerun`, same path as a live turn. This is the single "do we materialize a derived view?" fork in the data model, and the lazy answer (don't) holds because the source never changes.

### `revisions`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | the `revision_id` (`rev-1`, `rev-2`, …) |
| `message_id` | `uuid` FK → `messages` | `CASCADE` |
| `position` | `int` | the ordering; `GET …/revisions` returns it newest-first via `position DESC` |
| `source` | `TEXT` | `CHECK IN ('agent','rerun')` — contract: `rev-1` is `agent`, `rev-2+` are `rerun` |
| `sql` | `TEXT` | the full SQL — the input `rerun` re-executes, and the field `insights` may pin |
| `sql_preview` | `TEXT` | a short excerpt the contract's revision envelope returns without loading the full body |
| `flags` | `JSONB` | the sanity flags that applied at this revision (the *same* `flags` computed by `core/flags`, stored per revision so the tuning history is auditable) |
| `created_at` | `timestamptz` | |

- One row per (message, revision). `revisions` is how the message DTO's `revisions: ["rev-2","rev-1"]` list is built — a `SELECT position, id ORDER BY position DESC`.
- The insight pin (Gap B) references a `revision_id`, so `revisions.id` is the FK `insights.revision_id` points at. `revisions` is the *only* place the exact SQL a pin points at is stored; `insights.sql` is that row's `sql`, verbatim (below).

### `insights`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | the `insight_id` |
| `conversation_id` | `uuid` FK → `conversations` | `CASCADE` — the insight lives in the conversation, which is why `GET /v1/conversations/{id}/insights` is scoped |
| `message_id` | `uuid` FK → `messages` | `CASCADE` — the NL question that produced it (spec §7.2) |
| `revision_id` | `uuid` FK → `revisions` | **Gap B: the exact revision pinned**, not the message |
| `sql` | `TEXT` | stored *verbatim from the pin body* (the client proves the SQL it was looking at, per the contract) — equal to `revisions.sql` for this revision, duplicated deliberately so the insight is self-describing (the provenance trail reads as a narrative, spec §7.2) |
| `created_at` | `timestamptz` | |

- **1 insight → 0..n rules** (`rules.source_insight_id`). Not 1:1 — this is the `rule-lifecycle.md` freeze line made concrete: a rejected or under-covered rule leads to a *new* rule from the *same* insight, a sibling `rule_id`, not a transition of the first. The FK direction is insight → rules, so deleting the insight cascades all its rules (contract: `DELETE /v1/insights/{id}`).
- No `title`/`explanation` on the insight in v1 — the contract's insight detail is `source_message_id`, `revision_id`, and the pinned SQL. (An `explanation` column is a trivial add when the pin body grows one; not now.)

### `rules`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | the `rule_id` |
| `source_insight_id` | `uuid` FK → `insights` | `CASCADE` — "a rule can only originate from a pinned insight" (spec principle 5), enforced structurally by the FK |
| `title` | `TEXT` | the only freely-editable field (`PATCH …/rules/{id}`); cosmetic, not evidence |
| `where_clause` | `TEXT` | the rule's `WHERE`. **Frozen the instant a `backtest_results` row exists against it** (`rule-lifecycle.md` freeze line); editable only while `status='draft'` and no backtest row exists |
| `status` | `TEXT` | `CHECK IN ('draft','backtested','approved','deployed','rejected')` |
| `created_by` | `TEXT` | the FSM placeholder identity (spec §2 single-user) |
| `approved_by` | `TEXT` NULL | set by `approve` |
| `approved_at` | `timestamptz` NULL | set by `approve` |
| `disabled_at` | `timestamptz` NULL | the `disabled` **flag** (not a status) — set by `POST /v1/rules/{id}/disable`; `status` stays `'deployed'` |
| `created_at` | `timestamptz` | |

- `status` and `disabled_at` are the two orthogonal things the API returns about a rule's liveness. `GET /v1/rules?status=…` filters on `status` (a deployed-and-disabled rule still appears under `deployed`); `disabled_at` is the "and it's off now" marker.
- **No FK to a `users`/`identity` table.** `created_by`/`approved_by` are `TEXT` per spec §2 (a placeholder, single-user). A `user_id` FK would require a users table and an identity model that does not exist yet — the "prod where cheap" cost is real (a migration + a users table + an authn boundary) for a capability no one has asked for.

### `backtest_results`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | the `backtest_id` |
| `rule_id` | `uuid` FK → `rules` | `CASCADE` |
| `where_clause` | `TEXT` | **the specific `WHERE` this run was evaluated against** — stored so the row is self-contained, not derived from `rules.where_clause` (which could later be edited on a sibling rule). This makes the `rule-lifecycle.md` invariant ("each row is anchored to the `WHERE` live when it was written") *checkable in the row itself* |
| `window` | `TEXT` | `'full'` \| `'custom'` (the `window` field of the DTO) |
| `created_at` | `timestamptz` | |
| `metrics` | `JSONB` | `{precision, recall, false_positive_rate, baseline_fraud_rate, lift}` |
| `confusion_matrix` | `JSONB` | `{tp, fp, fn, tn}` |
| `coverage` | `JSONB` | `{matched_count, total_rows, total_fraud, support}` |
| `temporal_stability` | `JSONB` | `{earlier_slice: {…}, later_slice: {…}}` |
| `sample` | `JSONB` | `{count, columns, rows}` — the five matched rows the FSM eyeballs (Gap C). A JSONB column, not a child table: it is a capped, unqueried snapshot (5 rows), and "rows" here are *the backtest's* sample, not the reference table |

- `core/backtest.py` writes one row per `POST /v1/rules/{id}/backtest`; the metric math (the `compute_backtest` body in `db.py:174`, now in `core/`) is what produces these JSONB values. The LLM has no path to this table (ADR-0005 wall) and does not author any of it.
- The `draft → backtested` transition *is* the existence of a row here; the self-reloop (`backtested` → `backtested`) on a re-backtest is a second row against the same rule with a (possibly) different `window`.

### `deployment_records`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | the `deployment_id` |
| `rule_id` | `uuid` FK → `rules` | `CASCADE` |
| `backtest_id` | `uuid` FK → `backtest_results` | which backtest this deployment is *evidence* of |
| `external_rule_id` | `TEXT` | the fake ID the mock `core/rule_engine.deploy_rule` returned (spec §9) — stored as the only durable record of "this rule went out the door" |
| `payload` | `JSONB` | the *exact* payload the mock received (rule identity + provenance + full `BacktestResult`) — spec §9 |
| `deployed_at` | `timestamptz` | |

- One row per successful `deploy`; the `approved → deployed` transition is the existence of a row *and* a successful mock call. `GET /v1/rules/{id}/deployment` reads the latest row.
- The real rule engine, when it exists, replaces `core/rule_engine.py` with the same interface and this table is unchanged — the row and its `payload` are what get re-sent.

## The one diagram, in words

`conversations` 1—`runs` 1—`messages` 1—n `revisions`.
`messages` 1—n `insights` (scoped by `conversation_id`).
`insights` 1—n `rules`.
`rules` 1—n `backtest_results`.
`rules` 1—n `deployment_records`, each pinned to one `backtest_results`.

The object chain is linear on the "who produced what" axis; the only fan-out is a rule producing multiple backtests (tuning) and deployments (re-deploy), and an insight producing multiple sibling rules (the freeze-line retry path). Nothing fans into a message or a revision from "above."

## Phase gates (which tables alembic creates when)

| phase | tables created |
|---|---|
| P1 | `conversations`, `runs`, `messages`, `revisions` |
| P2 | `insights`, `rules`, `backtest_results`, `deployment_records` |
| P3 | — (the catalog is a `GET /v1/rules` *query over* `rules`, not a new table; `title` and any extra `rules` columns land here if the wireframes demand them) |

This is the ADR-0008 + ADR-0015 payoff: `alembic upgrade head` (running
as `app_rw`, non-superuser) on a fresh cluster reproduces the exact set
of `appstate` tables the current phase needs, and each P2/P3 addition is
a new revision, not a rewrite. The bootstrap (roles, schemas, the
`reference` SELECT grant) lives in `db-init/*.sql` + the seed — see
ADR-0015 for the split. The seed (`scripts/seed_reference.py`) is
separate and idempotent — it touches `reference` only, ever.

## Dependencies

- ADR-0007 (the two schemas / two roles; `reference_readonly` is the floor that makes `reference` read-only).
- ADR-0008 (Alembic owns all `appstate` DDL; the seed owns `reference` *data*).
- ADR-0015 (supersedes ADR-0008's "Alembic owns roles/schemas" clause: bootstrap DDL is in `db-init/*.sql`, the `reference` SELECT grant lives in the seed, Alembic runs as `app_rw`).
- ADR-0003 (the LangGraph checkpointer holds the run *trajectory*; the `runs` table here is the small identity/status row only).
- ADR-0005 (the "no LLM path into `backtest_results`/`deployment_records`" is the wall; the `agents → core` AST check is the running test).
- ADR-0006 (the `messages.grounding` JSONB *is* the structured contract, typed, so the column and the DTO cannot drift).
- `rule-lifecycle.md` (the state machine + freeze line that decide `rules.status`, `rules.disabled_at`, and why `backtest_results.where_clause` is stored rather than derived).
- spec §6.4/§7/§8/§9 (the object chain, the BacktestResult shape, the deployment payload).
- `data/db.py` — `compute_backtest` :line `174` is the metric math `core/backtest.py` ports; the `:line 6` join comment is the one `reference` fact to preserve.
