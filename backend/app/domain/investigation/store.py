from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.logger import get_logger
from app.domain.investigation.models import InvestigationSession

logger = get_logger(__name__)

# Location: app/data/investigation_sessions.db
DB_PATH = Path(__file__).resolve().parents[3] / "data" / "investigation_sessions.db"


def _ensure_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.debug("Ensuring sessions DB path: %s", DB_PATH)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            session_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def get_session(session_id: str) -> Optional[InvestigationSession]:
    try:
        conn = _ensure_db()
        cur = conn.execute("SELECT session_json FROM sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            logger.debug("Session not found in DB: %s", session_id)
            return None
        data = json.loads(row[0])
        logger.info("Loaded session from DB: %s", session_id)
        return InvestigationSession.model_validate(data)
    except Exception:
        # fallback to None on any DB error
        logger.exception("Failed to load session from DB, falling back to None")
        return None


def save_session(session: InvestigationSession) -> InvestigationSession:
    try:
        conn = _ensure_db()
        session_json = json.dumps(session.model_dump())
        now = datetime.utcnow().isoformat()
        conn.execute(
            "REPLACE INTO sessions (session_id, session_json, updated_at) VALUES (?, ?, ?)",
            (session.session_id, session_json, now),
        )
        conn.commit()
        conn.close()
        logger.info("Saved session to DB: %s steps=%d", session.session_id, len(session.steps))
        return session
    except Exception:
        logger.exception("Failed to save session to DB, falling back to in-memory save")
        # last-resort: keep session in-memory on module-level dict
        try:
            SESSIONS[session.session_id] = session
        except Exception:
            pass
        return session


# In-memory fallback store
SESSIONS: dict[str, InvestigationSession] = {}


def create_session(session_id: str, question: str) -> InvestigationSession:
    session = InvestigationSession(
        session_id=session_id,
        initial_question=question,
        steps=[],
    )
    logger.info("Creating session (store.create_session): %s", session_id)
    return save_session(session)

