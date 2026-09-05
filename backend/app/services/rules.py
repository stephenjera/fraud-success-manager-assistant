"""Rule-lifecycle services (spec §7 state machine, frozen contract).

Thin glue between the ``api`` routes and the two deterministic modules
this depends on:

- ``core/rule_state.py`` — the state machine (verb legality, the freeze
  line). Pure, no I/O.
- ``core/backtest.py`` — the two-universe computation. Reads ``reference``
  only. No writes to ``appstate``.

``services/`` owns all ``appstate`` writes for the P2 object chain.
The ADR-0005 wall holds: nothing in ``agents/`` reaches this module,
``core/`` does not reach it (the dependency is downward, not upward).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import psycopg

from app.api import (
    errors as api_errors,  # noqa: F401 - imported here to keep one error shape
)
from app.common.settings import settings
from app.core import backtest as core_backtest
from app.core import rule_engine as core_engine
from app.core import rule_state
from app.core import rules as core_rules
from app.services import store


def _con() -> psycopg.Connection:
    """A short-lived ``app_rw`` connection (autocommit; GC closes it at request end)."""
    return psycopg.connect(settings.appstate_dsn, autocommit=True)


def _jsonb(v: Any) -> str | None:
    return None if v is None else json.dumps(v)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


def pin_insight(
    *,
    conversation_id: str,
    message_id: str,
    revision_id: str,
    sql: str,
    explanation: str | None = None,
    rule_title: str | None = None,
    rule_where_clause: str | None = None,
    rule_rationale: str | None = None,
    rule_assumptions: list[str] | None = None,
) -> dict[str, Any]:
    """Create the insight row (Gap B: ``revision_id`` + ``sql`` are required).

    P5: model-proposed rule fields are stored alongside the insight.
    ``rule_where_clause`` is validated by ``core/rules`` if present.

    Verifies the revision belongs to the message, then inserts the row.
    Returns ``201``-shape: ``{insight_id, message_id, rev_id, sql, ...}``.

    Raises:
        api_errors.ApiError: A ``STATE_NOT_FOUND`` when the message or
            revision does not exist under this conversation.
    """
    # Scope the message to the conversation (404 if not found under it).
    store.get_message(conversation_id, message_id)
    row = (
        _con()
        .execute(
            "SELECT id FROM revisions WHERE id=%s AND message_id=%s",
            (revision_id, message_id),
        )
        .fetchone()
    )
    if row is None:
        raise api_errors.not_found(
            f"Revision {revision_id!r} not found under that message."
        )
    # P5: validate model-proposed clause if present (core/ gate).
    if rule_where_clause:
        try:
            rule_where_clause = core_rules.validate_where_clause(rule_where_clause)
        except ValueError as exc:
            raise api_errors.sql_rejected(
                "rule_where_clause failed core validation", rule_where_clause
            ) from exc
    assumptions_json = None
    if rule_assumptions:
        assumptions_json = json.dumps(rule_assumptions)
    ins = (
        _con()
        .execute(
            "INSERT INTO insights "
            "(conversation_id, message_id, revision_id, sql, explanation, "
            "rule_title, rule_where_clause, rule_rationale, rule_assumptions) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id::text, message_id::text, revision_id::text, sql, explanation, created_at, "
            "rule_title, rule_where_clause, rule_rationale, rule_assumptions",
            (
                conversation_id,
                message_id,
                revision_id,
                sql,
                explanation,
                rule_title,
                rule_where_clause,
                rule_rationale,
                assumptions_json,
            ),
        )
        .fetchone()
    )
    assert ins is not None  # INSERT … RETURNING always yields exactly one row
    raw_assumptions = ins[9]
    return {
        "insight_id": ins[0],
        "message_id": ins[1],
        "revision_id": ins[2],
        "sql": ins[3],
        "explanation": ins[4],
        "created_at": ins[5],
        "rule_title": ins[6],
        "rule_where_clause": ins[7],
        "rule_rationale": ins[8],
        "rule_assumptions": json.loads(raw_assumptions) if raw_assumptions else None,
    }


def get_insight(conversation_id: str, insight_id: str) -> dict[str, Any]:
    """The full insight detail (scoped to the conversation)."""
    if not store.is_uuid(insight_id):
        raise api_errors.not_found(f"Insight {insight_id!r} not in this conversation.")
    row = (
        _con()
        .execute(
            "SELECT i.id::text, i.message_id::text, i.revision_id::text, i.sql, i.explanation, "
            "       i.created_at, m.status AS message_status, m.run_id::text AS run_id, "
            "       (SELECT coalesce(json_agg(r.id::text ORDER BY r.position DESC),'[]') "
            "           FROM revisions r WHERE r.message_id = i.message_id) AS revisions, "
            "       (SELECT count(*) FROM rules rr WHERE rr.source_insight_id = i.id) AS rule_count "
            "FROM insights i JOIN messages m ON m.id = i.message_id "
            "WHERE i.id=%s AND i.conversation_id=%s",
            (insight_id, conversation_id),
        )
        .fetchone()
    )
    if row is None:
        raise api_errors.not_found(f"Insight {insight_id!r} not in this conversation.")
    return {
        "insight_id": row[0],
        "message_id": row[1],
        "revision_id": row[2],
        "sql": row[3],
        "explanation": row[4],
        "created_at": row[5],
        "message_status": row[6],
        "run_id": row[7],
        "revisions": json.loads(row[8]) if isinstance(row[8], str) else list(row[8]),
        "rule_count": int(row[9]),
    }


def list_insights(conversation_id: str) -> list[dict[str, Any]]:
    """The right rail: insight cards for one conversation."""
    store.get_conversation(conversation_id)  # 404 if the conversation is missing
    rows = (
        _con()
        .execute(
            "SELECT i.id::text, i.message_id::text, i.revision_id::text, i.sql, i.created_at, "
            "       (SELECT count(*) FROM rules rr WHERE rr.source_insight_id = i.id) AS rule_count "
            "FROM insights i WHERE i.conversation_id=%s ORDER BY i.created_at DESC",
            (conversation_id,),
        )
        .fetchall()
    )
    return [
        {
            "insight_id": r[0],
            "message_id": r[1],
            "revision_id": r[2],
            "sql": r[3],
            "created_at": r[4],
            "rule_count": int(r[5]),
        }
        for r in rows
    ]


def patch_insight(
    insight_id: str, *, sql: str | None, explanation: str | None
) -> dict[str, Any]:
    """Edit the pin before drafting (PATCH /v1/insights/{id})."""
    if not store.is_uuid(insight_id):
        raise api_errors.not_found(f"Insight {insight_id!r} not found.")
    row = (
        _con()
        .execute(
            "UPDATE insights SET "
            "  sql = COALESCE(%s, sql), "
            "  explanation = COALESCE(%s, explanation) "
            "WHERE id=%s RETURNING id::text, sql, explanation",
            (sql, explanation, insight_id),
        )
        .fetchone()
    )
    if row is None:
        raise api_errors.not_found(f"Insight {insight_id!r} not found.")
    return {"insight_id": row[0], "sql": row[1], "explanation": row[2]}


def delete_insight(insight_id: str) -> None:
    """Cascade-delete the insight (and its rules)."""
    if not store.is_uuid(insight_id):
        raise api_errors.not_found(f"Insight {insight_id!r} not found.")
    cur = _con().execute("DELETE FROM insights WHERE id=%s", (insight_id,))
    if cur.rowcount == 0:
        raise api_errors.not_found(f"Insight {insight_id!r} not found.")


# ---------------------------------------------------------------------------
# Rules: the state machine
# ---------------------------------------------------------------------------


def _get_rule(rule_id: str) -> dict[str, Any]:
    if not store.is_uuid(rule_id):
        raise api_errors.not_found(f"Rule {rule_id!r} not found.")
    row = (
        _con()
        .execute(
            "SELECT r.id::text, r.source_insight_id::text, r.title, r.where_clause, "
            "       r.status, r.created_by, r.approved_by, r.approved_at, "
            "       r.rationale, r.disabled_at, r.created_at "
            "FROM rules r WHERE r.id=%s",
            (rule_id,),
        )
        .fetchone()
    )
    if row is None:
        raise api_errors.not_found(f"Rule {rule_id!r} not found.")
    return {
        "rule_id": row[0],
        "source_insight_id": row[1],
        "title": row[2],
        "where_clause": row[3],
        "status": row[4],
        "created_by": row[5],
        "approved_by": row[6],
        "approved_at": row[7],
        "rationale": row[8],
        "disabled_at": row[9],
        "created_at": row[10],
    }


def rule_has_backtest(rule_id: str) -> bool:
    """The freeze-line gate: True iff any ``backtest_results`` row exists
    against this rule (the WHERE this row was written against is stored
    on the row itself — rule-lifecycle.md invariant)."""
    n = (
        _con()
        .execute("SELECT COUNT(*) FROM backtest_results WHERE rule_id=%s", (rule_id,))
        .fetchone()
    )
    assert n is not None  # COUNT(*) always returns a row
    return int(n[0]) > 0


def draft_rule(insight_id: str, *, title: str | None) -> dict[str, Any]:
    """POST /v1/insights/{id}/draft-rule — the only way a rule is born.

    P5: prefers model-proposed ``rule_where_clause`` stored on the insight
    over ``derive_where_clause(sql)``.  Falls back to derivation when the
    stored clause is None (backwards compat: insights pinned before P5,
    or from a SQL-only conversation without a model proposal).

    Enforces spec principle 5 (a rule only originates from a pinned
    insight) structurally: the FK is the enforcement, the agent is
    absent (the derivation is the deterministic mock that the FSM can
    override via ``PATCH /v1/rules/{id}``).
    """
    # The insight must exist and the rule must not already have been
    # drafted from it (a second draft from the same insight would be a
    # sibling rule, not a transition — the rule-lifecycle doc makes that explicit).
    if not store.is_uuid(insight_id):
        raise api_errors.not_found(f"Insight {insight_id!r} not found.")
    ins = (
        _con()
        .execute(
            "SELECT id::text, sql, rule_where_clause, rule_title, "
            "rule_rationale, rule_assumptions "
            "FROM insights WHERE id=%s",
            (insight_id,),
        )
        .fetchone()
    )
    if ins is None:
        raise api_errors.not_found(f"Insight {insight_id!r} not found.")
    # P5: prefer model-proposed clause; fall back to SQL derivation.
    if ins[2]:
        where = core_rules.validate_where_clause(ins[2])
    else:
        where = core_rules.derive_where_clause(ins[1])
    canonical = core_rules.validate_where_clause(where)
    chosen_title = title or ins[3] or "Unnamed rule"
    row = (
        _con()
        .execute(
            "INSERT INTO rules (source_insight_id, title, where_clause, status, created_by) "
            "VALUES (%s, %s, %s, 'draft', 'fsm') "
            "RETURNING id::text, source_insight_id::text, title, where_clause, status, created_at",
            (insight_id, chosen_title, canonical),
        )
        .fetchone()
    )
    assert row is not None  # INSERT … RETURNING always yields exactly one row
    # P5: use stored rationale/assumptions if present; fall back to defaults.
    stored_assumptions = ins[5]
    assumptions = (
        json.loads(stored_assumptions)
        if stored_assumptions
        else core_rules.assumptions_for(ins[1])
    )
    rationale = (
        ins[4]
        or "Rule proposed from this insight's pinned SQL. Edit the clause before backtesting."
    )
    return {
        "rule_id": row[0],
        "source_insight_id": row[1],
        "title": row[2],
        "where_clause": row[3],
        "status": row[4],
        "created_at": row[5],
        "draft_where": canonical,
        "rationale": rationale,
        "assumptions": assumptions,
    }


def get_rule(rule_id: str) -> dict[str, Any]:
    """Full rule detail: SQL, provenance, latest backtest, deployment record."""
    rule = _get_rule(rule_id)
    # Provenance: the pinned insight that produced this rule.
    ins = (
        _con()
        .execute(
            "SELECT i.id::text, i.message_id::text, i.revision_id::text, i.sql "
            "FROM insights i WHERE i.id=%s",
            (rule["source_insight_id"],),
        )
        .fetchone()
    )
    # Latest backtest (if any).
    bt = (
        _con()
        .execute(
            "SELECT id::text, where_clause, eval_window, created_at "
            "FROM backtest_results WHERE rule_id=%s ORDER BY created_at DESC LIMIT 1",
            (rule_id,),
        )
        .fetchone()
    )
    dep = (
        _con()
        .execute(
            "SELECT id::text, backtest_id::text, external_rule_id, deployed_at "
            "FROM deployment_records WHERE rule_id=%s ORDER BY deployed_at DESC LIMIT 1",
            (rule_id,),
        )
        .fetchone()
    )
    out = dict(rule)
    out["provenance"] = (
        {
            "source_insight_id": ins[0],
            "message_id": ins[1],
            "revision_id": ins[2],
            "sql": ins[3],
        }
        if ins
        else None
    )
    out["latest_backtest"] = (
        {
            "backtest_id": bt[0],
            "where_clause": bt[1],
            "window": bt[2],
            "created_at": bt[3],
        }
        if bt
        else None
    )
    out["deployment"] = (
        {
            "deployment_id": dep[0],
            "backtest_id": dep[1],
            "external_rule_id": dep[2],
            "deployed_at": dep[3],
        }
        if dep
        else None
    )
    return out


def list_rules(*, status: str | None, created_by: str | None) -> list[dict[str, Any]]:
    """The catalog (cross-conversation)."""
    where: list[str] = []
    params: list[Any] = []
    if status:
        where.append("r.status = %s")
        params.append(status)
    if created_by:
        where.append("r.created_by = %s")
        params.append(created_by)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = (
        _con()
        .execute(
            "SELECT r.id::text, r.source_insight_id::text, r.title, r.status, "
            "r.created_by, r.disabled_at, r.created_at, "
            "  (SELECT count(*) FROM backtest_results b WHERE b.rule_id = r.id) AS backtests, "
            "  (SELECT count(*) FROM deployment_records d WHERE d.rule_id = r.id) AS deployments "
            "FROM rules r" + where_sql + " ORDER BY r.created_at DESC",
            tuple(params),
        )
        .fetchall()
    )
    return [
        {
            "rule_id": r[0],
            "source_insight_id": r[1],
            "title": r[2],
            "status": r[3],
            "created_by": r[4],
            "disabled_at": r[5],
            "created_at": r[6],
            "backtests": int(r[7]),
            "deployments": int(r[8]),
        }
        for r in rows
    ]


def patch_rule(
    rule_id: str, *, title: str | None, where_clause: str | None
) -> dict[str, Any]:
    """PATCH /v1/rules/{id} — edit-and-own, with the freeze-line gate.

    The freeze line (rule-lifecycle.md): if a ``backtest_results`` row
    exists against this rule's current ``where_clause``, any
    ``where_clause`` change in the body → ``409 RULE_ILLEGAL_TRANSITION``.
    ``title`` is always editable (it is cosmetic, not evidence).
    A failed backtest writes no row, so a ``draft`` rule stays editable
    — the normal tune-the-clause loop.
    """
    rule = _get_rule(rule_id)
    if where_clause is not None and where_clause != rule["where_clause"]:
        if rule_has_backtest(rule_id):
            raise api_errors.ApiError(
                api_errors.RULE_ILLEGAL_TRANSITION,
                "The rule's WHERE is sealed (a backtest row already exists against it). "
                "To try a different clause, draft a new rule from the same insight.",
            )
        try:
            canonical = core_rules.validate_where_clause(where_clause)
        except core_rules.InvalidWhereClause as exc:
            raise api_errors.ApiError(
                api_errors.SQL_REJECTED,
                str(exc),
                details={"offending_clause": where_clause},
            ) from exc
        _con().execute(
            "UPDATE rules SET where_clause=%s WHERE id=%s",
            (canonical, rule_id),
        )
        if title is not None:
            _con().execute("UPDATE rules SET title=%s WHERE id=%s", (title, rule_id))
    elif title is not None:
        _con().execute("UPDATE rules SET title=%s WHERE id=%s", (title, rule_id))
    return _get_rule(rule_id)


def delete_rule(rule_id: str) -> None:
    """Cascade-delete the rule (and its backtest/deployment rows)."""
    if not store.is_uuid(rule_id):
        raise api_errors.not_found(f"Rule {rule_id!r} not found.")
    cur = _con().execute("DELETE FROM rules WHERE id=%s", (rule_id,))
    if cur.rowcount == 0:
        raise api_errors.not_found(f"Rule {rule_id!r} not found.")


def _assert_status(rule: dict[str, Any], verb: str) -> None:
    """Run the state machine: raise ``409 RULE_ILLEGAL_TRANSITION`` on illegal."""
    try:
        rule_state.apply(rule["status"], verb)
    except rule_state.RuleIllegalTransition as exc:
        raise api_errors.ApiError(
            api_errors.RULE_ILLEGAL_TRANSITION,
            str(exc),
            details={"verb": verb, "current": rule["status"]},
        ) from exc


def backtest_rule(rule_id: str, *, window: str | None = None) -> dict[str, Any]:
    """POST /v1/rules/{id}/backtest — the command, never invoked by the LLM.

    Deterministic, read-only over ``reference``. The state machine
    decides if the rule is allowed (draft/backtested only), then
    ``core/backtest.run`` does the math, and the row is written last
    (the existence of the row *is* the transition — rule-lifecycle.md).
    """
    rule = _get_rule(rule_id)
    _assert_status(rule, "backtest")
    try:
        result = core_backtest.run(
            rule_id=rule_id,
            clause=rule["where_clause"],
            window=window or "full",
        )
    except core_rules.InvalidWhereClause as exc:
        # A bad clause is ``SQL_REJECTED`` (the FSM can fix the clause and retry).
        raise api_errors.ApiError(
            api_errors.SQL_REJECTED,
            str(exc),
            details={"offending_clause": rule["where_clause"]},
        ) from exc
    except psycopg.Error as exc:
        raise api_errors.ApiError(
            api_errors.INTERNAL_ERROR,
            "Backtest could not be evaluated against the reference data.",
            details={"error": str(exc)},
        ) from exc
    row = (
        _con()
        .execute(
            "INSERT INTO backtest_results (rule_id, where_clause, eval_window, labeled_only, full_universe, temporal_stability, sample) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id::text, created_at",
            (
                rule_id,
                rule["where_clause"],
                window or "full",
                _jsonb(result.labeled_only.as_block("labeled_only")),
                _jsonb(result.full_universe.as_block("full_universe")),
                _jsonb(result.temporal_stability),
                _jsonb(result.sample),
            ),
        )
        .fetchone()
    )
    assert row is not None  # INSERT … RETURNING always yields exactly one row
    # The transition "draft → backtested" is the row. Re-read to reflect it.
    updated = _get_rule(rule_id)
    if updated["status"] == rule_state.DRAFT:
        _con().execute("UPDATE rules SET status='backtested' WHERE id=%s", (rule_id,))
    dto = result.as_dto(
        rule_id=rule_id, window=window or "full", where_clause=rule["where_clause"]
    )
    dto["backtest_id"] = row[0]
    dto["created_at"] = row[1].isoformat() if isinstance(row[1], datetime) else row[1]
    # ADR-0014: each per-universe block already carries its own
    # confusion_matrix + metrics + coverage; the top-level fields are the
    # shared ones (sample, window, temporal).
    return dto


def backtests_for_rule(rule_id: str) -> list[dict[str, Any]]:
    """GET /v1/rules/{id}/backtests — the tuning history."""
    _get_rule(rule_id)  # 404 if missing
    rows = (
        _con()
        .execute(
            "SELECT id::text, where_clause, eval_window, created_at, "
            "       (labeled_only->'metrics'->>'precision') AS lo_precision, "
            "       (labeled_only->'metrics'->>'lift') AS lo_lift "
            "FROM backtest_results WHERE rule_id=%s ORDER BY created_at DESC",
            (rule_id,),
        )
        .fetchall()
    )
    return [
        {
            "backtest_id": r[0],
            "where_clause": r[1],
            "window": r[2],
            "created_at": r[3],
            "labeled_only_precision": float(r[4]) if r[4] is not None else None,
            "labeled_only_lift": float(r[5]) if r[5] is not None else None,
        }
        for r in rows
    ]


def get_backtest(rule_id: str, backtest_id: str) -> dict[str, Any]:
    """GET /v1/rules/{id}/backtests/{bid} — one full report."""
    _get_rule(rule_id)  # 404 if the rule is missing
    row = (
        _con()
        .execute(
            "SELECT id::text, where_clause, eval_window, created_at, labeled_only, full_universe, temporal_stability, sample "
            "FROM backtest_results WHERE id=%s AND rule_id=%s",
            (backtest_id, rule_id),
        )
        .fetchone()
    )
    if row is None:
        raise api_errors.not_found(f"Backtest {backtest_id!r} not found for this rule.")
    return {
        "backtest_id": row[0],
        "rule_id": rule_id,
        "created_at": row[3],
        "window": row[2],
        "where_clause": row[1],
        "labeled_only": _maybe_json(row[4]),
        "full_universe": _maybe_json(row[5]),
        "temporal_stability": _maybe_json(row[6]) or {},
        "sample": _maybe_json(row[7]),
    }


def _maybe_json(raw: Any) -> Any:
    return raw if (raw is None or isinstance(raw, (dict, list))) else json.loads(raw)


def approve(rule_id: str, actor: str, rationale: str) -> dict[str, Any]:
    """POST /v1/rules/{id}/approve — FSM-explicit, from ``backtested`` only."""
    rule = _get_rule(rule_id)
    _assert_status(rule, "approve")
    _con().execute(
        "UPDATE rules SET status='approved', approved_by=%s, approved_at=now(), rationale=%s "
        "WHERE id=%s",
        (actor, rationale, rule_id),
    )
    updated = _get_rule(rule_id)
    return {
        "rule_id": rule_id,
        "status": updated["status"],
        "approved_by": updated["approved_by"],
        "approved_at": updated["approved_at"],
        "rationale": updated["rationale"],
    }


def reject(rule_id: str, actor: str, rationale: str) -> dict[str, Any]:
    """POST /v1/rules/{id}/reject — terminal, from ``backtested`` only."""
    rule = _get_rule(rule_id)
    _assert_status(rule, "reject")
    _con().execute(
        "UPDATE rules SET status='rejected', rationale=%s WHERE id=%s",
        (rationale, rule_id),
    )
    updated = _get_rule(rule_id)
    return {
        "rule_id": rule_id,
        "status": updated["status"],
        "rationale": updated["rationale"],
        "actor": actor,
    }


def deploy_rule(rule_id: str) -> dict[str, Any]:
    """POST /v1/rules/{id}/deploy — FSM-explicit, from ``approved`` only.

    Assembles the payload (spec §9), calls the (mock) rule engine,
    and writes the durable ``deployment_records`` row. The fake
    external id comes back from the engine and is the only durable
    record that "this rule was sent."
    """
    rule = _get_rule(rule_id)
    _assert_status(rule, "deploy")
    # The latest backtest is the evidence this deployment references (spec §9).
    bt = (
        _con()
        .execute(
            "SELECT id::text, where_clause, eval_window, created_at, labeled_only, full_universe, sample "
            "FROM backtest_results WHERE rule_id=%s ORDER BY created_at DESC LIMIT 1",
            (rule_id,),
        )
        .fetchone()
    )
    if bt is None:
        raise api_errors.ApiError(
            api_errors.RULE_ILLEGAL_TRANSITION,
            "A rule must have at least one backtest before it can be deployed.",
        )
    latest_backtest = {
        "backtest_id": bt[0],
        "where_clause": bt[1],
        "window": bt[2],
        "created_at": bt[3].isoformat() if isinstance(bt[3], datetime) else bt[3],
        "labeled_only": _maybe_json(bt[4]),
        "full_universe": _maybe_json(bt[5]),
        "sample": _maybe_json(bt[6]),
    }
    payload = {
        "rule_id": rule_id,
        "version": "1",
        "where_clause": rule["where_clause"],
        "title": rule["title"],
        "provenance": {
            "source_insight_id": rule["source_insight_id"],
            "created_by": rule["created_by"],
            "approved_by": rule["approved_by"],
            "approved_at": rule["approved_at"].isoformat()
            if rule["approved_at"]
            else None,
            "rationale": rule["rationale"],
        },
        "latest_backtest": latest_backtest,
    }
    external_rule_id = core_engine.client().deploy_rule(payload)
    row = (
        _con()
        .execute(
            "INSERT INTO deployment_records (rule_id, backtest_id, external_rule_id, payload) "
            "VALUES (%s, %s, %s, %s) RETURNING id::text, deployed_at",
            (rule_id, bt[0], external_rule_id, _jsonb(payload)),
        )
        .fetchone()
    )
    assert row is not None  # INSERT … RETURNING always yields exactly one row
    _con().execute("UPDATE rules SET status='deployed' WHERE id=%s", (rule_id,))
    return {
        "deployment_id": row[0],
        "rule_id": rule_id,
        "backtest_id": bt[0],
        "external_rule_id": external_rule_id,
        "status": "deployed",
        "deployed_at": row[1],
    }


def deploy_status(rule_id: str) -> dict[str, Any]:
    """GET /v1/rules/{id}/deployment — the current deployed state."""
    _get_rule(rule_id)  # 404 if the rule is missing
    row = (
        _con()
        .execute(
            "SELECT id::text, backtest_id::text, external_rule_id, deployed_at "
            "FROM deployment_records WHERE rule_id=%s ORDER BY deployed_at DESC LIMIT 1",
            (rule_id,),
        )
        .fetchone()
    )
    if row is None:
        return {"rule_id": rule_id, "deployment": None, "status": "not-deployed"}
    return {
        "rule_id": rule_id,
        "deployment": {
            "deployment_id": row[0],
            "backtest_id": row[1],
            "external_rule_id": row[2],
            "deployed_at": row[3],
        },
        "status": "deployed",
    }


def disable_rule(rule_id: str) -> dict[str, Any]:
    """POST /v1/rules/{id}/disable — post-deploy flag, from ``deployed`` only.

    A disabled rule still has ``status='deployed'``; ``disabled_at`` is
    the "we stopped using this one" marker (rule-lifecycle.md). The
    mock rule engine sees the flag so the receiving side also learns.
    """
    rule = _get_rule(rule_id)
    _assert_status(rule, "disable")
    dep = (
        _con()
        .execute(
            "SELECT id::text, external_rule_id FROM deployment_records WHERE rule_id=%s ORDER BY deployed_at DESC LIMIT 1",
            (rule_id,),
        )
        .fetchone()
    )
    if dep is None:
        raise api_errors.ApiError(
            api_errors.RULE_ILLEGAL_TRANSITION,
            "A rule can only be disabled after it has been deployed.",
        )
    core_engine.client().disable_rule(dep[1])
    _con().execute("UPDATE rules SET disabled_at=now() WHERE id=%s", (rule_id,))
    return {
        "rule_id": rule_id,
        "deployment_id": dep[0],
        "disabled_at": datetime.now(tz=UTC),
        "status": "deployed",
    }


__all__ = [
    "pin_insight",
    "get_insight",
    "list_insights",
    "patch_insight",
    "delete_insight",
    "draft_rule",
    "get_rule",
    "list_rules",
    "patch_rule",
    "delete_rule",
    "backtest_rule",
    "backtests_for_rule",
    "get_backtest",
    "approve",
    "reject",
    "deploy_rule",
    "deploy_status",
    "disable_rule",
]
