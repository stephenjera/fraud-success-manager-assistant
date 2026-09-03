"""Durable appstate over the ``app_rw`` role (ADR-0007).

Small read/write helpers for the four P1 tables (``conversations``, ``runs``,
``messages``, ``revisions``). Every connection is the ``app_rw`` role scoped to
``appstate``; there is no path from here to ``reference`` or to the model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

from app.common.settings import settings


class NotFound(KeyError):
    """The appstate row does not exist (surfaces as ``STATE_NOT_FOUND``)."""


@dataclass(slots=True)
class MessageRow:
    """A row of ``appstate.messages`` with its loaded grounding/error/revisions."""

    message_id: str
    run_id: str
    conversation_id: str
    status: str
    created_at: datetime
    grounding: dict[str, Any] | None
    error: dict[str, Any] | None
    revisions: list[str]


def _con() -> psycopg.Connection:
    return psycopg.connect(settings.appstate_dsn, autocommit=True)


def create_conversation() -> tuple[str, datetime]:
    """Insert a conversation; return ``(id, created_at)``."""
    with _con() as con:
        row = con.execute("INSERT INTO conversations DEFAULT VALUES RETURNING id::text, created_at").fetchone()
    return row[0], row[1]


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    with _con() as con:
        row = con.execute(
            "SELECT id::text, created_at, last_active FROM conversations WHERE id=%s", (conversation_id,)
        ).fetchone()
    if row is None:
        return None
    return {"conversation_id": row[0], "created_at": row[1], "last_active": row[2]}


def list_conversations() -> list[dict[str, Any]]:
    with _con() as con:
        rows = con.execute(
            "SELECT c.id::text, c.created_at, c.last_active, "
            "(SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) "
            "FROM conversations c ORDER BY c.last_active DESC"
        ).fetchall()
    return [
        {
            "conversation_id": r[0],
            "created_at": r[1],
            "last_active": r[2],
            "message_count": int(r[3]),
        }
        for r in rows
    ]


def delete_conversation(conversation_id: str) -> None:
    with _con() as con:
        cur = con.execute("DELETE FROM conversations WHERE id=%s", (conversation_id,))
        if cur.rowcount == 0:
            raise NotFound(conversation_id)


def create_turn(conversation_id: str, text: str) -> tuple[str, str]:
    """Durally create a run + message; return ``(run_id, message_id)``.

    The message and its ``agent`` revision (rev-1) are written now so a dropped
    stream never loses the answer (ADR-0011). Status starts ``running``.
    """
    with _con() as con:
        cur = con.execute(
            "INSERT INTO runs (conversation_id, status) VALUES (%s, 'running') RETURNING id::text",
            (conversation_id,),
        )
        run_id = cur.fetchone()[0]
        cur = con.execute(
            "INSERT INTO messages (conversation_id, run_id, status) VALUES (%s, %s, 'running') "
            "RETURNING id::text, created_at",
            (conversation_id, run_id),
        )
        message_id, created_at = cur.fetchone()
        # rev-1 = the agent's draft (written when the grounding lands, not now).
        con.execute("UPDATE conversations SET last_active = %s WHERE id=%s", (created_at, conversation_id))
    return run_id, message_id


def set_result(run_id: str, message_id: str, success: bool, status: str, grounding: dict | None, error: dict | None,
              sql: str | None, sql_preview: str) -> None:
    """Terminal write: message status + grounding/error; the agent revision (rev-1)."""
    with _con() as con:
        con.execute(
            "UPDATE messages SET status=%s, grounding=%s, error=%s WHERE id=%s",
            (status, _jsonb(grounding), _jsonb(error), message_id),
        )
        if sql is not None:
            con.execute(
                "INSERT INTO revisions (message_id, position, source, sql, sql_preview, flags) "
                "VALUES (%s, 1, 'agent', %s, %s, %s)",
                (message_id, sql, sql_preview, _jsonb((grounding or {}).get("flags", []) if grounding else [])),
            )
        con.execute(
            "UPDATE runs SET status=%s, finished_at=now(), message_id=%s WHERE id=%s",
            (status, message_id, run_id),
        )


def add_rerun(message_id: str, sql: str, sql_preview: str, result: dict[str, Any], flags: list[str]) -> str:
    """A ``rerun`` revision (rev-N); return ``(message_id, revision_id)``-style id.

    Next ``position`` = existing max + 1 (rev-2, rev-3, …).
    """
    with _con() as con:
        pos = int(con.execute("SELECT coalesce(max(position),0)+1 FROM revisions WHERE message_id=%s", (message_id,)).fetchone()[0])
        row = con.execute(
            "INSERT INTO revisions (message_id, position, source, sql, sql_preview, flags) "
            "VALUES (%s, %s, 'rerun', %s, %s, %s) RETURNING id::text",
            (message_id, pos, sql, sql_preview, _jsonb(flags)),
        ).fetchone()
        # rerun also carries the result for the sync response (result is not stored;
        # the durable fact is sql + flags — see data-model.md "no result-rows column").
    return row[0]


def get_message(conversation_id: str, message_id: str) -> MessageRow:
    with _con() as con:
        row = con.execute(
            "SELECT id::text, run_id::text, conversation_id::text, status, created_at, grounding, error "
            "FROM messages WHERE id=%s AND conversation_id=%s",
            (message_id, conversation_id),
        ).fetchone()
        if row is None:
            raise NotFound(message_id)
        revs = con.execute(
            "SELECT id::text FROM revisions WHERE message_id=%s ORDER BY position DESC", (message_id,)
        ).fetchall()
    return MessageRow(
        message_id=row[0],
        run_id=row[1],
        conversation_id=row[2],
        status=row[3],
        created_at=row[4],
        grounding=row[5],
        error=row[6],
        revisions=[r[0] for r in revs],
    )


def list_messages(conversation_id: str) -> list[dict[str, Any]]:
    with _con() as con:
        rows = con.execute(
            "SELECT id::text, run_id::text, status, created_at, (grounding IS NOT NULL) "
            "FROM messages WHERE conversation_id=%s ORDER BY created_at ASC",
            (conversation_id,),
        ).fetchall()
    return [
        {"message_id": r[0], "run_id": r[1], "status": r[2], "created_at": r[3], "grounded": bool(r[4])}
        for r in rows
    ]


def get_run(run_id: str) -> dict[str, Any] | None:
    with _con() as con:
        row = con.execute(
            "SELECT id::text, conversation_id::text, message_id::text, status, created_at FROM runs WHERE id=%s",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "run_id": row[0],
        "conversation_id": row[1],
        "message_id": row[2],
        "status": row[3],
        "created_at": row[4],
        "finished_at": None,
    }


def list_revisions(message_id: str) -> list[dict[str, Any]]:
    """All revisions for a message, newest-first (the tuning-history read)."""
    with _con() as con:
        rows = con.execute(
            "SELECT id::text, created_at, sql_preview, source FROM revisions WHERE message_id=%s ORDER BY position DESC",
            (message_id,),
        ).fetchall()
    return [{"revision_id": r[0], "created_at": r[1], "sql_preview": r[2], "source": r[3]} for r in rows]


def latest_revision(message_id: str) -> dict[str, Any] | None:
    """The newest revision (used when grounding should reflect the live edit)."""
    with _con() as con:
        row = con.execute(
            "SELECT id::text, position, source, sql, sql_preview, flags, created_at "
            "FROM revisions WHERE message_id=%s ORDER BY position DESC LIMIT 1",
            (message_id,),
        ).fetchone()
    if row is None:
        return None
    return {"revision_id": row[0], "position": row[1], "source": row[2], "sql": row[3], "sql_preview": row[4], "flags": row[5]}


def _jsonb(value: Any) -> str | None:
    """Serialise to JSON text for a JSONB column (psycopg needs a str/bytes, not a dict)."""
    return None if value is None else json.dumps(value)


def revision_preview(sql: str, limit: int = 120) -> str:
    """A short ``sql_preview`` for the revisions envelope."""
    flat = " ".join(sql.split())
    return flat[:limit] + ("…" if len(flat) > limit else "")
