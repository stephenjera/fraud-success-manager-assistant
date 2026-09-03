"""Deterministic sanity flags over a query result (ADR-0006 fact field).

The flags are a property of the *result set*, not of the model — they are
computed here, not reported by the LLM (that is the ADR-0005 wall showing
through: the flag list is assertable against a known result, model-independent).
"""

from __future__ import annotations


class Result:
    """A capped read result, the shape ``run_sql`` and ``rerun`` both return."""

    __slots__ = ("columns", "rows", "row_cap", "truncated")

    def __init__(self, columns: list[str], rows: list[list[object]], row_cap: int, truncated: bool) -> None:
        """Store the columns, capped rows, cap, and whether more existed."""
        self.columns = columns
        self.rows = rows
        self.row_cap = row_cap
        self.truncated = truncated

    def to_dict(self) -> dict[str, object]:
        """The ``result`` body the rerun response and rerun revision carry."""
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_cap": self.row_cap,
            "truncated": self.truncated,
        }


def _large(result_rows: int, total_rows: int | None) -> bool:
    """A big fraction of a large table, uncapped (the analyst may be surprised)."""
    if not total_rows or total_rows < 1000:
        return False
    return result_rows / total_rows >= 0.05


def run(result: Result, total_rows: int | None = None) -> list[str]:
    """Compute the deterministic flag set for a result.

    Args:
        result: The capped read.
        total_rows: Total rows in the primary table, if known.

    Returns:
        Ordered flag names: ``empty_result`` / ``row_cap_hit`` / ``large_result``.
    """
    flags: list[str] = []
    if not result.rows:
        flags.append("empty_result")
    if result.truncated:
        flags.append("row_cap_hit")
    if _large(len(result.rows), total_rows):
        flags.append("large_result")
    return flags


_ROW_CAP = 100


def row_cap() -> int:
    """The cap the reader applies and returns alongside ``truncated``."""
    return _ROW_CAP
