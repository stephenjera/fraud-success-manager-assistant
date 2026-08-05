"""
Persistent session store powered by SQLite.

Serialises pydantic_ai ModelMessage objects via ModelMessagesTypeAdapter,
stores them alongside session metadata and execution logs in a local
SQLite database so chat history survives backend restarts.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_ai.messages import ModelMessagesTypeAdapter

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Import for type-checkers only to avoid a runtime circular import
    from app.api.services.session import ExecutionEvent
else:
    ExecutionEvent = Any
from app.config import settings
from app.logger import get_logger

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage

logger = get_logger("session_store")

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_SESSIONS_DB_PATH = _DB_DIR / "sessions.db"


# ---------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_json TEXT    NOT NULL,
    order_index  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    event_json   TEXT    NOT NULL,
    logged_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, order_index);
CREATE INDEX IF NOT EXISTS idx_exec_session ON execution_logs(session_id);
"""


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_SESSIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.info("Sessions database initialised at %s", _SESSIONS_DB_PATH)
    finally:
        conn.close()


def expire_old_sessions() -> int:
    ttl = timedelta(hours=settings.SESSION_TTL_HOURS)
    cutoff = datetime.now(UTC) - ttl
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE updated_at < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info("Expired %d session(s) older than %dh", deleted, settings.SESSION_TTL_HOURS)
    finally:
        conn.close()
    return deleted


# ---------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------

def _messages_to_json(msgs: list[ModelMessage]) -> str:
    return ModelMessagesTypeAdapter.dump_json(msgs).decode()


def _json_to_messages(data: str) -> list[ModelMessage]:
    return ModelMessagesTypeAdapter.validate_json(data)


def _event_to_json(event: ExecutionEvent) -> str:
    return json.dumps({
        "sql": event.sql,
        "columns": event.columns,
        "row_count": event.row_count,
        "preview_rows": event.preview_rows,
        "execution_ms": event.execution_ms,
    })


def _json_to_event(data: str) -> ExecutionEvent:
    obj = json.loads(data)
    return ExecutionEvent(
        sql=obj["sql"],
        columns=obj.get("columns"),
        row_count=obj.get("row_count"),
        preview_rows=obj.get("preview_rows"),
        execution_ms=obj.get("execution_ms"),
    )


# ---------------------------------------------------------------
# Public interface — drops in for SessionManager / ExecutionStore
# ---------------------------------------------------------------

def ensure_session(session_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ? AND updated_at != ?",
            (now, session_id, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(session_id: str) -> list[ModelMessage]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT message_json FROM chat_messages WHERE session_id = ? ORDER BY order_index",
            (session_id,),
        ).fetchall()
        msgs: list[ModelMessage] = []
        for row in rows:
            msgs.extend(_json_to_messages(row["message_json"]))
        return msgs
    except Exception:
        logger.exception("Failed to load chat history for session %s", session_id)
        return []
    finally:
        conn.close()


def save_chat_messages(session_id: str, messages: list[ModelMessage]) -> None:
    ensure_session(session_id)
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        for idx, msg in enumerate(messages):
            conn.execute(
                "INSERT INTO chat_messages (session_id, message_json, order_index) VALUES (?, ?, ?)",
                (session_id, _messages_to_json([msg]), idx),
            )
        conn.commit()
    except Exception:
        logger.exception("Failed to save chat messages for session %s", session_id)
    finally:
        conn.close()


def append_execution_event(session_id: str, event: ExecutionEvent) -> None:
    ensure_session(session_id)
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO execution_logs (session_id, event_json, logged_at) VALUES (?, ?, ?)",
            (session_id, _event_to_json(event), datetime.now(UTC).isoformat()),
        )
        conn.commit()
    except Exception:
        logger.exception("Failed to append execution event for session %s", session_id)
    finally:
        conn.close()


def get_execution_events(session_id: str) -> list[ExecutionEvent]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT event_json FROM execution_logs WHERE session_id = ? ORDER BY logged_at",
            (session_id,),
        ).fetchall()
        return [_json_to_event(row["event_json"]) for row in rows]
    except Exception:
        logger.exception("Failed to load execution events for session %s", session_id)
        return []
    finally:
        conn.close()


def list_sessions() -> list[dict[str, str]]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT id, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to list sessions")
        return []
    finally:
        conn.close()


def delete_session(session_id: str) -> bool:
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        logger.exception("Failed to delete session %s", session_id)
        return False
    finally:
        conn.close()


def extract_conversation_text(messages: list[ModelMessage]) -> list[dict[str, str]]:
    """Return a simplified transcript the frontend can render directly."""
    items: list[dict[str, str]] = []
    for msg in messages:
        role = msg.__class__.__name__.replace("Model", "").replace("Message", "").lower()
        try:
            content = " ".join(
                [p.content for p in msg.parts if hasattr(p, "content")]
            )
        except Exception:
            content = str(msg)
        items.append({"role": role, "content": content})
    return items


def session_count() -> int:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()
