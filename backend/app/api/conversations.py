"""Conversations + the explore loop (ADR-0011 command/query split).

The command (``POST …/messages``) durably creates the run, returns 201, and starts
the agent on a worker thread. The answer is read back via ``GET …/messages/{mid}``
(the durable fact) or streamed via ``GET /v1/runs/{run_id}/events`` (the view).
``rerun`` is a synchronous deterministic re-execute — a wall-reuse, not a run (Gap H).
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.api import envelope, errors
from app.core import db as core_db
from app.core import flags as core_flags
from app.core import sql_validator
from app.services import run as run_service
from app.services import store

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


class MessageIn(BaseModel):
    """The analyst's natural-language question."""

    text: str


class RerunIn(BaseModel):
    """The FSM's edited SQL for a synchronous re-execute (Gap H)."""

    sql: str


@router.post("", status_code=201)
def create_conversation() -> dict[str, Any]:
    """New session. ``201 {conversation_id, created_at}``."""
    cid, created_at = store.create_conversation()
    return {"conversation_id": cid, "created_at": created_at}


@router.get("")
def list_conversations() -> dict[str, Any]:
    """The sidebar: an envelope of conversation summaries."""
    return envelope.envelope(store.list_conversations())


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, Any]:
    """Session detail: the conversation plus its durable message transcript."""
    conv = store.get_conversation(conversation_id)
    if conv is None:
        raise errors.not_found(f"Conversation {conversation_id!r} not found.")
    conv["messages"] = store.list_messages(conversation_id)
    return conv


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str) -> Response:
    """Cascade-delete the conversation (→ its messages)."""
    try:
        store.delete_conversation(conversation_id)
    except store.NotFound as exc:
        raise errors.not_found(f"Conversation {conversation_id!r} not found.") from exc
    return Response(status_code=204)


@router.post("/{conversation_id}/messages", status_code=201)
def post_message(conversation_id: str, body: MessageIn) -> dict[str, Any]:
    """The command: durably create the run + message, start the agent, return 201.

    The answer is not in this response — it is fetched under ``message_id`` or
    streamed under ``run_id`` (ADR-0011).
    """
    if store.get_conversation(conversation_id) is None:
        raise errors.not_found(f"Conversation {conversation_id!r} not found.")
    run_id, message_id = store.create_turn(conversation_id, body.text)
    threading.Thread(
        target=run_service.execute,
        args=(conversation_id, message_id, run_id, body.text),
        daemon=True,
    ).start()
    return {"message_id": message_id, "run_id": run_id, "status": "running"}


@router.get("/{conversation_id}/messages")
def list_messages(conversation_id: str) -> dict[str, Any]:
    """The transcript (durable): an envelope of turn summaries."""
    if store.get_conversation(conversation_id) is None:
        raise errors.not_found(f"Conversation {conversation_id!r} not found.")
    return envelope.envelope(store.list_messages(conversation_id))


@router.get("/{conversation_id}/messages/{message_id}")
def get_message(conversation_id: str, message_id: str) -> dict[str, Any]:
    """The message DTO (Gap A union-typed): the canonical, durable read of the answer."""
    try:
        row = store.get_message(conversation_id, message_id)
    except store.NotFound as exc:
        raise errors.not_found(f"Message {message_id!r} not found.") from exc
    return {
        "message_id": row.message_id,
        "run_id": row.run_id,
        "status": row.status,
        "created_at": row.created_at,
        "grounding": row.grounding,
        "error": row.error,
        "revisions": row.revisions,
    }


@router.get("/{conversation_id}/messages/{message_id}/revisions")
def get_revisions(conversation_id: str, message_id: str) -> dict[str, Any]:
    """The tuning history: an envelope of ``{revision_id, created_at, sql_preview, source}``."""
    try:
        store.get_message(conversation_id, message_id)
    except store.NotFound as exc:
        raise errors.not_found(f"Message {message_id!r} not found.") from exc
    return envelope.envelope(store.list_revisions(message_id))


@router.post("/{conversation_id}/messages/{message_id}/rerun")
def rerun(conversation_id: str, message_id: str, body: RerunIn) -> dict[str, Any]:
    """Synchronous deterministic re-execute of the edited SQL (Gap H). No run, no stream.

    Reuses the same wall as the agent: ``validate_sql`` (ADR-0002) then execute.
    """
    try:
        store.get_message(conversation_id, message_id)
    except store.NotFound as exc:
        raise errors.not_found(f"Message {message_id!r} not found.") from exc
    try:
        safe = sql_validator.validate_sql(body.sql)
    except sql_validator.SqlRejected as exc:
        raise errors.sql_rejected(exc.reason, exc.sql) from exc
    try:
        result = core_db.run_readonly_query(safe)
    except core_db.SqlExecutionError as exc:
        raise errors.ApiError(errors.INTERNAL_ERROR, "The SQL failed to execute against the reference data.", details={"error": str(exc)}) from exc
    total = core_db.count_rows(sql_validator.primary_table(body.sql) or "")
    fl = core_flags.run(result, total_rows=total)
    preview = store.revision_preview(body.sql)
    revision_id = store.add_rerun(message_id, body.sql, preview, result.to_dict(), fl)
    return {
        "message_id": message_id,
        "revision_id": revision_id,
        "result": result.to_dict(),
        "flags": fl,
    }
