"""Guard for the `nulls` computation in `profile_column`.

The bug (fixed 2026-09-03): `nulls = total - non_null_count`. A fully
populated column (e.g. `cards.card_type`, 3437 rows, 0 NULLs) reported
`nulls == 3437`, telling the model the column was empty. The invariant this
test pins: `nulls` must equal the count the `IS NULL` query returns —
independent of `total` and `non_null` — so a column with 0 NULL rows returns
`nulls == 0`.

We monkeypatch `psycopg.connect` (the tool needs it but we don't want the
test to require a live Postgres daemon). The SQL is deterministic; the fake
cursor sequence returns the counts we set.
"""

from __future__ import annotations

import json
from typing import Any

import pytest


class _FakeCursor:
    """Serves a flat, ordered row sequence to successive fetches.

    ``profile_column`` uses ONE cursor for four queries: three
    ``fetchone()`` (the COUNTs) then one ``fetchall()`` (the top-N samples).
    So the flat list ``[(100,), (20,), (3,), ('A',), ('B',), ('C',)]`` maps
    1-to-1 onto those five fetches regardless of how many ``cursor()`` calls
    the (single) ``with`` block issues.
    """

    def __init__(self, rows: list[Any]) -> None:
        self._rows = list(rows)

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *a: Any) -> None:
        return None

    def execute(self, _sql: Any) -> None:
        return None

    def fetchone(self) -> Any:
        return self._rows.pop(0)

    def fetchall(self) -> list[Any]:
        out = self._rows
        self._rows = []
        return out


class _FakeConn:
    def __init__(self, rows: list[Any]) -> None:
        self._cursor = _FakeCursor(rows)

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def close(self) -> None:
        return None


def _tool(profile_column: Any) -> Any:
    """`@tool` wraps the function; call via `.func` (langchain convention)."""
    return profile_column.func if hasattr(profile_column, "func") else profile_column


def test_null_is_null_count_not_inverted_total(monkeypatch: pytest.MonkeyPatch) -> None:
    # Flat row sequence, one per fetch in order:
    #   COUNT(*)            -> (100,)
    #   COUNT(*) WHERE=NULL -> (20,)   <- `nulls` must equal this value
    #   COUNT(DISTINCT)     -> (3,)
    #   SELECT ... LIMIT 3  -> ('A',), ('B',), ('C',)
    # A revert to the old `nulls = total - X` formula cannot produce 20 here.
    monkeypatch.setattr(
        "app.agents.graph.psycopg.connect",
        lambda *a, **kw: _FakeConn([(100,), (20,), (3,), ("A",), ("B",), ("C",)]),
    )
    from app.agents.graph import profile_column

    out = json.loads(_tool(profile_column)("cards", "card_type"))
    assert out["total"] == 100
    assert out["nulls"] == 20
    assert out["distinct"] == 3
    assert out["top"] == ["A", "B", "C"]


def test_fully_populated_column_reports_zero_nulls(monkeypatch: pytest.MonkeyPatch) -> None:
    # The real regression case (2026-09-03): `cards.card_type` had 0 NULLs but
    # the buggy formula returned `nulls == total` (3437), hiding the values.
    # Pinned: a fully-populated column reports `nulls == 0`.
    monkeypatch.setattr(
        "app.agents.graph.psycopg.connect",
        lambda *a, **kw: _FakeConn([(3437,), (0,), (3,), ("Credit",), ("Credit",), ("Credit",), ("Credit",), ("Credit",)]),
    )
    from app.agents.graph import profile_column

    out = json.loads(_tool(profile_column)("cards", "card_type"))
    assert out["total"] == 3437
    assert out["nulls"] == 0, f"fully-populated column must report nulls==0, got {out['nulls']}"

