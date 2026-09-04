"""P1 revision: the four ``appstate`` tables (conversations, runs, messages, revisions).

Revision ID: 0001_p1_baseline
Revises:
Create Date: 2026-09-03 (rewritten under ADR-0015)

Scope (ADR-0015): this revision manages *tables only*. The two roles, the two
schemas, and the GRANTs are infrastructure owned by ``db-init/001-roles.sql`` +
``db-init/002-schemas.sql`` (idempotent entrypoint/repair scripts), and the
``reference`` tables+data are owned by ``scripts/seed_reference.py``. This keeps
Alembic doing what it does best — orderable table DDL — and out of role/schema
provisioning, which is exactly the coupling that let a ``downgrade`` rename the
seeded ``reference`` schema and strip its grants (see ADR-0015 incident).

Runs as ``app_rw`` (owns the ``appstate`` schema via 002-schemas.sql), so the
``downgrade`` below is a plain ``DROP TABLE`` — it cannot touch ``reference``,
the roles, or the schema itself.
"""

from __future__ import annotations

from alembic import op

revision = "0001_p1_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE appstate.conversations ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  last_active TIMESTAMPTZ NOT NULL DEFAULT now()"
        ");"
    )
    op.execute(
        "CREATE TABLE appstate.runs ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  conversation_id UUID NOT NULL REFERENCES appstate.conversations(id) ON DELETE CASCADE,"
        "  message_id UUID,"
        "  status TEXT NOT NULL CHECK (status IN ('running','success','error','timeout')),"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  finished_at TIMESTAMPTZ"
        ");"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS runs_conv_ix ON appstate.runs (conversation_id);"
    )
    op.execute(
        "CREATE TABLE appstate.messages ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  conversation_id UUID NOT NULL REFERENCES appstate.conversations(id) ON DELETE CASCADE,"
        "  run_id UUID NOT NULL REFERENCES appstate.runs(id) ON DELETE CASCADE,"
        "  status TEXT NOT NULL CHECK (status IN ('running','success','error','timeout')),"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  grounding JSONB,"
        "  error JSONB"
        ");"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS messages_conv_ix ON appstate.messages (conversation_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS messages_run_ix ON appstate.messages (run_id);"
    )
    op.execute(
        "CREATE TABLE appstate.revisions ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  message_id UUID NOT NULL REFERENCES appstate.messages(id) ON DELETE CASCADE,"
        "  position INTEGER NOT NULL,"
        "  source TEXT NOT NULL CHECK (source IN ('agent','rerun')),"
        "  sql TEXT NOT NULL,"
        "  sql_preview TEXT NOT NULL,"
        "  flags JSONB NOT NULL DEFAULT '[]'::jsonb,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  UNIQUE (message_id, position)"
        ");"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS revisions_msg_ix ON appstate.revisions (message_id);"
    )


def downgrade() -> None:
    # Plain DROP TABLE — no schema rename, no role/grant changes. ``app_rw`` owns only
    # these tables; it cannot drop the schema or touch ``reference``, so a mistyped
    # downgrade here is boring and reversible (re-run ``upgrade head``).
    op.execute("DROP TABLE IF EXISTS appstate.revisions;")
    op.execute("DROP TABLE IF EXISTS appstate.messages;")
    op.execute("DROP TABLE IF EXISTS appstate.runs;")
    op.execute("DROP TABLE IF EXISTS appstate.conversations;")
