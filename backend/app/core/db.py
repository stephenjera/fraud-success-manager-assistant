"""Read the reference data as ``reference_readonly`` (ADR-0007).

The agent's only door to data: a synchronous reader that executes a validated
read-only SELECT capped at :data:`ROW_CAP` rows. The connection target is
``settings.reference_dsn`` (the read-only role), so a write is a permission
error at the Postgres layer, not a caught exception — the role is the floor.
A ``SET search_path = reference`` per connection makes ``reference.*`` visible
unqualified, without touching the SQL the model wrote.
"""

from __future__ import annotations

import psycopg
from psycopg import sql

from app.common.settings import settings
from app.core import flags, sql_validator


class SqlExecutionError(RuntimeError):
    """The validated SQL failed to execute against the reference role."""


def _connect() -> psycopg.Connection:
    """A read-only connection scoped to the ``reference`` schema."""
    con = psycopg.connect(settings.reference_dsn, autocommit=True)
    with con.cursor() as cur:
        cur.execute("SET search_path = reference")
    return con


def run_readonly_query(sql_text: str) -> flags.Result:
    """Execute a validated SELECT as ``reference_readonly``; return a capped result.

    Args:
        sql_text: A single read-only SELECT (validated here).

    Returns:
        A :class:`flags.Result` (``columns`` / capped ``rows`` / cap / ``truncated``).

    Raises:
        SqlRejected: If the SQL is not a single read-only SELECT.
        SqlExecutionError: If execution fails (role or statement error).
    """
    safe = sql_validator.validate_sql(sql_text)
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute(safe)
            cols = [d.name for d in cur.description or []]
            rows: list[list[object]] = []
            truncated = False
            for row in cur:
                if len(rows) >= flags.row_cap():
                    truncated = True
                    break
                rows.append(list(row))
    except sql_validator.SqlRejected:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced as SqlExecutionError
        raise SqlExecutionError(str(exc)) from exc
    finally:
        con.close()
    return flags.Result(
        columns=cols, rows=rows, row_cap=flags.row_cap(), truncated=truncated
    )


def count_rows(table: str) -> int | None:
    """Total rows in a ``reference`` table (for the ``large_result`` flag) or ``None``.

    Args:
        table: A bare table name in the ``reference`` schema.

    Returns:
        The row count, or ``None`` when the table is unsafe/nonexistent.
    """
    if not table.isidentifier():
        return None
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
            )
            row = cur.fetchone()
            assert row is not None  # COUNT(*) always returns a row
            return int(row[0])
    except Exception:  # noqa: BLE001 - unknown table is not a fatal flag-input
        return None
    finally:
        con.close()
