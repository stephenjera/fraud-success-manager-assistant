"""P2 revision: insights, rules, backtest_results, deployment_records.

Revision ID: 0002_p2_rules
Revises: 0001_p1_baseline
Create Date: 2026-09-03 (rewritten under ADR-0015)

Creates the P2 object chain (data-model.md ``appstate``):
``insights`` → ``rules`` → ``backtest_results`` ← ``deployment_records``.

Scope (ADR-0015): tables only. ``app_rw`` owns the ``appstate`` schema (set by
``db-init/002-schemas.sql``), so tables it creates are ``app_rw``-owned by
default — no ``ALTER ... OWNER`` needed, and ``downgrade`` is a plain
``DROP TABLE`` it cannot escalate into (it cannot drop the schema, the
roles, or touch ``reference``). ADR-0014 is honoured: ``labeled_only`` and
``full_universe`` are two self-contained JSONB blocks (each carries its own
``confusion_matrix`` / ``metrics`` / ``coverage`` / ``temporal_stability``),
and ``sample`` is the shared capped row set the FSM eyeballs.
"""

from __future__ import annotations

from alembic import op

revision = "0002_p2_rules"
down_revision = "0001_p1_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- insights (one source of truth per pinned revision) ---
    op.execute(
        "CREATE TABLE appstate.insights ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  conversation_id UUID NOT NULL REFERENCES appstate.conversations(id) ON DELETE CASCADE,"
        "  message_id UUID NOT NULL REFERENCES appstate.messages(id) ON DELETE CASCADE,"
        "  revision_id UUID NOT NULL REFERENCES appstate.revisions(id) ON DELETE CASCADE,"
        "  sql TEXT NOT NULL,"
        "  explanation TEXT,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ");"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS insights_conv_ix ON appstate.insights (conversation_id);"
    )

    # --- rules (the state machine: draft → backtested → approved → deployed | rejected) ---
    op.execute(
        "CREATE TABLE appstate.rules ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  source_insight_id UUID NOT NULL REFERENCES appstate.insights(id) ON DELETE CASCADE,"
        "  title TEXT NOT NULL,"
        "  where_clause TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','backtested','approved','deployed','rejected')),"
        "  created_by TEXT NOT NULL,"
        "  approved_by TEXT,"
        "  approved_at TIMESTAMPTZ,"
        "  rationale TEXT,"
        "  disabled_at TIMESTAMPTZ,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ");"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS rules_insight_ix ON appstate.rules (source_insight_id);"
    )

    # --- backtest_results (one row per POST …/backtest; the freeze-line anchor) ---
    # ADR-0014: two self-contained universes. `labeled_only` and `full_universe`
    # are each {confusion_matrix, metrics, coverage}; `temporal_stability` is the
    # shared top-level block (median-date split, ADR-0014); `sample` is the shared
    # capped row set the FSM eyeballs. JSONB because nothing filters *into* them
    # (no ?precision=… query) — the DTO 1:1-maps onto the columns (data-model.md).
    op.execute(
        "CREATE TABLE appstate.backtest_results ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  rule_id UUID NOT NULL REFERENCES appstate.rules(id) ON DELETE CASCADE,"
        "  eval_window TEXT NOT NULL DEFAULT 'full',"
        "  where_clause TEXT NOT NULL,"
        "  labeled_only JSONB NOT NULL,"
        "  full_universe JSONB NOT NULL,"
        "  temporal_stability JSONB NOT NULL,"
        "  sample JSONB NOT NULL,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ");"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS backtests_rule_ix ON appstate.backtest_results (rule_id);"
    )

    # --- deployment_records (the durable artifact of a mocked deploy) ---
    op.execute(
        "CREATE TABLE appstate.deployment_records ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  rule_id UUID NOT NULL REFERENCES appstate.rules(id) ON DELETE CASCADE,"
        "  backtest_id UUID NOT NULL REFERENCES appstate.backtest_results(id) ON DELETE RESTRICT,"
        "  external_rule_id TEXT NOT NULL,"
        "  payload JSONB NOT NULL,"
        "  deployed_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ");"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS deployments_rule_ix ON appstate.deployment_records (rule_id);"
    )


def downgrade() -> None:
    # Plain DROP TABLE — no schema/role/grant changes. ``app_rw`` owns only these
    # tables, so a wrong downgrade here is boring and reversible (re-run head).
    op.execute("DROP TABLE IF EXISTS appstate.deployment_records;")
    op.execute("DROP TABLE IF EXISTS appstate.backtest_results;")
    op.execute("DROP TABLE IF EXISTS appstate.rules;")
    op.execute("DROP TABLE IF EXISTS appstate.insights;")
