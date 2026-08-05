"""Query safety guardrails for SQL execution."""

import re
from typing import Final

from app.config import settings

UNSAFE_STATEMENTS: Final[set[str]] = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
    "ATTACH", "DETACH", "BEGIN", "COMMIT", "ROLLBACK",
    "PRAGMA", "VACUUM", "ANALYZE", "EXPLAIN",
}

LIMIT_PATTERN = re.compile(r"\bLIMIT\b", re.IGNORECASE)

MAX_SELECT_STATEMENTS = 3


def validate_statement_type(sql: str) -> str | None:
    """Reject non-SELECT statements.

    Returns an error message if the query is unsafe, None if it passes.
    """
    stripped = sql.strip().lstrip("- (")
    token = stripped.split()[0].upper() if stripped.split() else ""

    if token in UNSAFE_STATEMENTS:
        return f"Rejected unsafe statement: {token}"

    select_count = len(re.findall(r"(?<!\w)SELECT\b", sql, re.IGNORECASE))
    if select_count > MAX_SELECT_STATEMENTS:
        return f"Too many SELECT clauses ({select_count} found, max {MAX_SELECT_STATEMENTS})"

    return None


def enforce_row_limit(sql: str, max_rows: int | None = None) -> str:
    """Append a LIMIT clause if the query has no LIMIT.

    Args:
        sql: The query string to sanitize.
        max_rows: Override for the row cap (defaults to ``QUERY_MAX_ROWS``).

    Returns:
        The query string with a LIMIT clause appended if needed.
    """
    if max_rows is None:
        max_rows = settings.QUERY_MAX_ROWS

    clean = sql.strip().rstrip(";")

    if LIMIT_PATTERN.search(clean):
        return clean.rstrip(";") + ";"

    return f"{clean} LIMIT {max_rows};"
