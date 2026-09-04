"""sqlglot SQL guard (ADR-0002): admit a single read-only SELECT, else reject.

Defense-in-depth on top of the ``reference_readonly`` role (ADR-0007): the
role is the floor, this is the first gate the agent's SQL meets. A rejection
here surfaces as ``SQL_REJECTED`` at the API edge (``api/errors.py``).
"""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

_DIALECT = "postgres"
# AST node types that can never be part of a read-only SELECT.
_FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Merge,
    exp.Command,  # SET / SHOW / \copy / VACUUM / …
)
# ponytail: the reference_readonly role is the real write-block. This keyword
# scan only guards against a future, permissive sqlglot accepting a write that
# still contains a forbidden token; cheap, and removable if sqlglot alone is
# ever trusted. It is a floor on top of a floor.
_FORBIDDEN_TOKENS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "TRUNCATE",
    "COPY",
    "VACUUM",
    "ANALYZE",
    "MERGE",
    "ATTACH",
    "DETACH",
)


class SqlRejected(ValueError):
    """The validator refused the SQL. ``sql`` preserves the offending text."""

    def __init__(self, reason: str, sql: str) -> None:
        """Carry the human ``reason`` and the offending ``sql`` for the error detail."""
        super().__init__(reason)
        self.reason = reason
        self.sql = sql


def validate_sql(sql: str) -> str:
    """Admit a single read-only Postgres SELECT; else raise :class:`SqlRejected`.

    Args:
        sql: The candidate statement.

    Returns:
        The normalised (pretty-printed) SELECT, safe to execute read-only.

    Raises:
        SqlRejected: If it is not a single read-only SELECT.
    """
    text = (sql or "").strip().rstrip(";").rstrip()
    if not text:
        raise SqlRejected("Empty SQL.", text)
    # A single statement is checked via sqlglot (len(parsed) == 1) below; a real
    # multi-statement with a mid-string `;` is caught there. We only strip the
    # decorative trailing `;` the model likes to add.
    token = next(
        (t for t in _FORBIDDEN_TOKENS if re.search(rf"\b{t}\b", text, re.IGNORECASE)),
        None,
    )
    if token:
        raise SqlRejected(f"Read-only SELECT only (found {token!r}).", text)

    parsed = sqlglot.parse(text, read=_DIALECT)
    if not parsed:
        raise SqlRejected("Could not parse as SQL.", text)
    if len(parsed) != 1:
        raise SqlRejected("A single statement only.", text)
    ast = parsed[0]
    if not isinstance(ast, exp.Select) or isinstance(ast, _FORBIDDEN_NODES):
        raise SqlRejected(f"Read-only SELECT only (got {type(ast).__name__}).", text)
    return ast.sql(dialect=_DIALECT)


def primary_table(sql: str) -> str | None:
    """The first table a SELECT reads from (for the total-row sanity flag).

    Args:
        sql: A validated SELECT.

    Returns:
        The table name, or ``None`` when the statement has no table.
    """
    table = sqlglot.parse_one(sql, read=_DIALECT).find(exp.Table)
    return table.name if table else None
