"""Rule routes — the P2 lifecycle (spec §7 state machine, frozen contract).

Edge over ``services.rules``: every route in the contract, the same
error shape (``api.errors``), and no direct DB access. The state
machine is in ``core/rule_state.py``; the freeze-line gate is
``services.rules.patch_rule`` — the 409 for an edit-after-backtest is
the contract's exact wording.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.api import envelope
from app.services import rules

router = APIRouter(prefix="/v1/rules", tags=["rules"])


class PatchRuleIn(BaseModel):
    """PATCH body: ``title`` and/or ``where_clause`` (the edit-and-own body)."""

    title: str | None = None
    where_clause: str | None = None


class RationaleIn(BaseModel):
    """approve/reject body: ``{rationale, actor}`` (spec §7)."""

    rationale: str
    actor: str


class BacktestIn(BaseModel):
    """Optional backtest body: a window (``"full"`` or ``"custom"``)."""

    window: Literal["full", "custom"] | None = None


@router.get("")
def list_rules(
    status: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """The Catalog — cross-conversation, filterable (spec §13)."""
    items = rules.list_rules(status=status, created_by=created_by)
    return envelope.envelope(items)


@router.get("/{rule_id}")
def get_rule(rule_id: str) -> dict[str, Any]:
    """Full rule detail: SQL, provenance, latest backtest, deployment record."""
    return rules.get_rule(rule_id)


@router.patch("/{rule_id}")
def patch_rule(rule_id: str, body: PatchRuleIn) -> dict[str, Any]:
    """Edit-and-own. The freeze line (409) lives in the service."""
    return rules.patch_rule(rule_id, title=body.title, where_clause=body.where_clause)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str) -> Response:
    """Cascade-delete the rule (and its backtest + deployment rows)."""
    rules.delete_rule(rule_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Backtest (the command, never the agent)
# ---------------------------------------------------------------------------


@router.post("/{rule_id}/backtest", status_code=201)
def backtest(rule_id: str, body: BacktestIn | None = None) -> dict[str, Any]:
    """POST …/backtest — deterministic, never LLM (spec §7.4)."""
    return rules.backtest_rule(rule_id, window=body.window if body else None)


@router.get("/{rule_id}/backtests")
def list_backtests(rule_id: str) -> dict[str, Any]:
    """The tuning history: an envelope of backtest summaries."""
    return envelope.envelope(rules.backtests_for_rule(rule_id))


@router.get("/{rule_id}/backtests/{backtest_id}")
def get_backtest(rule_id: str, backtest_id: str) -> dict[str, Any]:
    """One full BacktestResult (Gap C)."""
    return rules.get_backtest(rule_id, backtest_id)


# ---------------------------------------------------------------------------
# Approve / reject / deploy / disable
# ---------------------------------------------------------------------------


@router.post("/{rule_id}/approve")
def approve(rule_id: str, body: RationaleIn) -> dict[str, Any]:
    """POST …/approve — FSM-explicit, from ``backtested`` only."""
    return rules.approve(rule_id, actor=body.actor, rationale=body.rationale)


@router.post("/{rule_id}/reject")
def reject(rule_id: str, body: RationaleIn) -> dict[str, Any]:
    """POST …/reject — terminal, from ``backtested`` only."""
    return rules.reject(rule_id, actor=body.actor, rationale=body.rationale)


@router.post("/{rule_id}/deploy", status_code=201)
def deploy(rule_id: str) -> dict[str, Any]:
    """POST …/deploy — FSM-explicit, from ``approved`` only. Mock engine."""
    return rules.deploy_rule(rule_id)


@router.post("/{rule_id}/disable")
def disable(rule_id: str) -> dict[str, Any]:
    """POST …/disable — a post-deploy flag on a ``deployed`` rule."""
    return rules.disable_rule(rule_id)


@router.get("/{rule_id}/deployment")
def get_deployment(rule_id: str) -> dict[str, Any]:
    """GET …/deployment — the current deployment record (or null)."""
    return rules.deploy_status(rule_id)


__all__ = ["router"]
