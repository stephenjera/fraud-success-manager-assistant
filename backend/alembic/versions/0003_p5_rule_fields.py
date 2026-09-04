"""P5: model-proposed rule fields on insights.

Revision ID: 0003_p5_rule_fields
Revises: 0002_p2_rules
Create Date: 2026-09-04

``insight`` rows can now carry a model-proposed rule directly (no SQL
needed — the agent fills these when it spots a pattern but the data
can't answer).  The four columns parallel the shape the model's
``rule_proposal`` tool returns and are all nullable (an insight pinned
from SQL-only conversation won't have them).

``core/rules.validate_where_clause`` still gates the clause.
``services/rules.draft_rule`` prefers the stored clause over derivation.
"""

from __future__ import annotations

from alembic import op

revision = "0003_p5_rule_fields"
down_revision = "0002_p2_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: skip if column already present (e.g. manual DDL in dev).
    for col, typ in [
        ("rule_title", "TEXT"),
        ("rule_where_clause", "TEXT"),
        ("rule_rationale", "TEXT"),
        ("rule_assumptions", "JSONB"),
    ]:
        op.execute(
            f"DO $$ BEGIN "
            f"ALTER TABLE appstate.insights ADD COLUMN {col} {typ}; "
            f"EXCEPTION WHEN duplicate_column THEN NULL; END $$;"
        )


def downgrade() -> None:
    op.execute("ALTER TABLE appstate.insights DROP COLUMN IF EXISTS rule_assumptions;")
    op.execute("ALTER TABLE appstate.insights DROP COLUMN IF EXISTS rule_rationale;")
    op.execute("ALTER TABLE appstate.insights DROP COLUMN IF EXISTS rule_where_clause;")
    op.execute("ALTER TABLE appstate.insights DROP COLUMN IF EXISTS rule_title;")
