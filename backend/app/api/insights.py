"""Insight routes (spec §7.2 — pin before drafting a rule).

The pin DTO (api-contract.md Gap B) requires ``revision_id`` and ``sql``
— the client proves which query they saw. ``services.rules`` owns the
row; this file is only the HTTP edge.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.api import envelope, errors
from app.services import rules, store


router = APIRouter(prefix="/v1", tags=["insights"])


class PinInsightBody(BaseModel):
    """The Gap B pin body: ``revision_id`` + ``sql`` are required."""

    message_id: str
    revision_id: str
    sql: str
    explanation: str | None = None


class PatchInsightBody(BaseModel):
    """The PATCH body: edit the pin before drafting a rule (optional fields)."""

    sql: str | None = None
    explanation: str | None = None


class DraftRuleIn(BaseModel):
    """Optional draft body: a title override. The LLM does not write the clause."""

    title: str | None = None


def _require_conversation(conversation_id: str) -> None:
    if store.get_conversation(conversation_id) is None:
        raise errors.not_found(f"Conversation {conversation_id!r} not found.")


@router.post("/conversations/{conversation_id}/insights", status_code=201)
def pin(conversation_id: str, body: PinInsightBody) -> dict[str, Any]:
    """Create an insight — the pin (Gap B)."""
    _require_conversation(conversation_id)
    return rules.pin_insight(
        conversation_id=conversation_id,
        message_id=body.message_id,
        revision_id=body.revision_id,
        sql=body.sql,
        explanation=body.explanation,
    )


@router.get("/conversations/{conversation_id}/insights")
def list_insights(conversation_id: str) -> dict[str, Any]:
    """The right rail: insight cards for this conversation (an envelope)."""
    _require_conversation(conversation_id)
    return envelope.envelope(rules.list_insights(conversation_id))


@router.get("/insights/{insight_id}")
def get_insight(insight_id: str) -> dict[str, Any]:
    """Full insight detail (the rail card)."""
    # The contract scopes insights to a conversation, but the detail
    # lookup is by id — resolve the owning conversation from the row,
    # then hand off to the service (which re-checks the scope).
    row = rules._con().execute(  # noqa: SLF001 - a single row lookup for the id→scope shortcut
        "SELECT conversation_id::text FROM insights WHERE id=%s",
        (insight_id,),
    ).fetchone()
    if row is None:
        raise errors.not_found(f"Insight {insight_id!r} not found.")
    return rules.get_insight(row[0], insight_id)


@router.patch("/insights/{insight_id}")
def patch_insight(insight_id: str, body: PatchInsightBody) -> dict[str, Any]:
    """Edit the pin (sql / explanation) before drafting a rule."""
    return rules.patch_insight(insight_id, sql=body.sql, explanation=body.explanation)


@router.delete("/insights/{insight_id}", status_code=204)
def delete_insight(insight_id: str) -> Response:
    """Cascade-delete the insight (and any rules derived from it)."""
    rules.delete_insight(insight_id)
    return Response(status_code=204)


@router.post("/insights/{insight_id}/draft-rule", status_code=201)
def draft_rule(insight_id: str, body: DraftRuleIn | None = None) -> dict[str, Any]:
    """The pin → draft bridge (spec §7.2 FSM-explicit action).

    Returns the new rule plus the draft's rationale and assumptions
    (the ADR-0006 structured output shape, not free prose).
    """
    return rules.draft_rule(insight_id, title=body.title if body else None)


__all__ = ["router"]
