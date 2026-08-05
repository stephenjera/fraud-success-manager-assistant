"""Session management endpoints for listing, loading, and deleting conversations."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionHistoryItem,
    SessionHistoryResponse,
    SessionItem,
    SessionListResponse,
)
from app.api.services import session_store as _store
from app.logger import get_logger

router = APIRouter()
logger = get_logger("sessions")


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions_endpoint() -> SessionListResponse:
    """Return all active sessions ordered by most recently updated."""
    sessions = _store.list_sessions()
    items = [
        SessionItem(
            id=s["id"],
            created_at=s["created_at"],
            updated_at=s["updated_at"],
        )
        for s in sessions
    ]
    return SessionListResponse(sessions=items)


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
def load_session_history(session_id: str) -> SessionHistoryResponse:
    """
    Return the chat transcript for a session in frontend-friendly format.

    Returns simplified role + content pairs (not raw ModelMessage objects).
    """
    messages = _store.get_chat_history(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found or empty")
    items: list[SessionHistoryItem] = []
    for msg in _store.extract_conversation_text(messages):
        items.append(
            SessionHistoryItem(
                role=msg["role"],
                content=msg["content"],
            )
        )
    return SessionHistoryResponse(session_id=session_id, history=items)


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
def delete_session_endpoint(session_id: str) -> SessionDeleteResponse:
    """Delete a session and all associated data (chat history + execution logs)."""
    deleted = _store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info("Deleted session %s", session_id)
    return SessionDeleteResponse(deleted=True)


@router.post("/sessions", response_model=SessionCreateResponse)
def create_session_endpoint() -> SessionCreateResponse:
    """Create a fresh session and return its ID."""
    session_id = f"sess_{secrets.token_hex(8)}"
    _store.ensure_session(session_id)
    return SessionCreateResponse(session_id=session_id)


@router.post("/sessions/cleanup")
def cleanup_expired_sessions() -> dict[str, int]:
    """Manually trigger expiration of sessions older than SESSION_TTL_HOURS."""
    deleted = _store.expire_old_sessions()
    return {"expired_count": deleted, "remaining": _store.session_count()}
