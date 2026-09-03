"""Core rule-derivation and WHERE-clause validity — deterministic, no LLM, no DB.

The ADR-0005 wall: ``core/`` is pure logic. :func:`derive_where_clause`
turns a pinned insight into a rule's initial ``where_clause`` + the
draft rationale/assumptions (the mock bridge for
``POST /v1/insights/{id}/draft-rule``); :func:`validate_where_clause`
is the gate every rule's clause passes before it can be evaluated
against the reference data.

``services/`` is the only caller — the agent has no import path here.
"""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp

_DIALECT = "postgres"

# The join basis ADR-0014 allows a rule to reference. Anything else is a
# ``fraud_labels``/``merchants``-style table the FSM did not intend.
_ALLOWED_TABLES = frozenset({
    "transactions", "fraud_labels", "cards", "merchants", "users",
    "mcc_codes", "merchant_locations",
})

# AST node shapes a WHERE clause must not contain: subqueries and CTEs
# would smuggle a second query past the "single expression" contract.
_FORBIDDEN_EXPR = (exp.Subquery, exp.CTE)


class InvalidWhereClause(ValueError):
    """The clause is not a safe single expression over the join basis."""


def _condition(sql_text: str) -> exp.Expression | None:
    """Re-parse a fragment as a condition, or ``None`` when it is not one."""
    text = (sql_text or "").strip().rstrip(";").rstrip()
    if not text:
        return None
    try:
        expr: exp.Expression = sqlglot.parse_one(text, read=_DIALECT, into=exp.Condition)
    except sqlglot.errors.ParseError:  # noqa: PERF203 - single guarded call
        return None
    return expr if expr is not None and not isinstance(expr, _FORBIDDEN_EXPR) else None


def derive_where_clause(pinned_sql: str) -> str:
    """The pinned insight's SQL → the rule's initial ``where_clause``.

    The deterministic mock for the spec's "agent proposes a ``WHERE``":
    the rule is the pinned query's own filter — no model call, no
    non-determinism, assertable without an LLM. A ``1=1`` clause is
    returned when the pinned query has no explicit filter (still a valid
    clause; the backtest will simply match everything the basis allows).
    """
    text = (pinned_sql or "").strip()
    parse = sqlglot.parse(text, read=_DIALECT)
    select = next((ast for ast in parse if isinstance(ast, exp.Select)), None)
    where = select.args.get("where") if select else None
    if where is not None and where.this is not None:
        clause = where.this
        if isinstance(clause, (exp.Paren, exp.Bracket)) and clause.this is not None:
            clause = clause.this
        if clause is not None:
            out = clause.sql(dialect=_DIALECT)
            if out and out.upper() not in {"1", "TRUE"}:
                return out
    return "1=1"


def table_names(sql_text: str) -> list[str]:
    """The tables a SQL fragment references (order-independent)."""
    nodes = sqlglot.parse(sql_text, read=_DIALECT) or [sqlglot.maybe_parse(sql_text, read=_DIALECT)]
    tables: list[str] = []
    for node in nodes:
        if node is None:
            continue
        for t in node.find_all(exp.Table):
            name = t.name
            if name and name not in tables:
                tables.append(name)
    return tables


def has_joins(pinned_sql: str) -> bool:
    """True when the pinned query crosses more than one table."""
    return bool(sqlglot.parse_one(pinned_sql, read=_DIALECT).find(exp.Join))


def assumptions_for(pinned_sql: str) -> list[str]:
    """The draft's assumptions (spec §6.4: provenance, not prose)."""
    assumptions = [
        "Pinned from the query's revision; the clause is that query's own filter, verbatim.",
    ]
    if has_joins(pinned_sql):
        assumptions.append("Cross-table joins preserved (cards, merchants, users reachable per ADR-0014).")
    assessments = "1=1" if derive_where_clause(pinned_sql) == "1=1" else "explicit"
    assumptions.append(f"Label coverage: the clause filters a {assessments} condition over the ADR-0014 basis.")
    return assumptions


def validate_where_clause(clause: str) -> str:
    """Gate a rule's ``where_clause`` before it is evaluated by the backtest.

    Args:
        clause: The candidate clause.

    Returns:
        The normalised clause (canonical whitespace / case per ``postgres``).

    Raises:
        InvalidWhereClause: If the clause is empty, unparseable, a
            sub-query/CTE, or references a table outside the ADR-0014 basis.
    """
    cond = _condition(clause)
    if cond is None:
        raise InvalidWhereClause("WHERE clause is empty or not a single condition.")
    for table in table_names(clause):
        if table.lower() not in _ALLOWED_TABLES:
            raise InvalidWhereClause(f"Table {table!r} is outside the ADR-0014 basis.")
    return cond.sql(dialect=_DIALECT)


def looks_like_where_clause(text: str) -> bool:
    """Cheap text check used by :func:`derive_where_clause` fallbacks."""
    return bool(re.search(r"\bWHERE\b", text or "", re.IGNORECASE))


__all__ = [
    "InvalidWhereClause",
    "derive_where_clause",
    "table_names",
    "has_joins",
    "assumptions_for",
    "validate_where_clause",
    "looks_like_where_clause",
]
