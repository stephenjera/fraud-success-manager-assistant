"""Shared fixtures for the P1 API tests.

The LLM is faked so the whole suite is fast and deterministic; Postgres and the
``store`` stay real (the DB is a genuine P1 dependency), and any test that needs
it skips cleanly when Postgres is unreachable instead of failing on connection.

Fakes installed here (module-level seams, patched per-test via ``monkeypatch``):
- ``app.services.run._graph``  -> a graph whose ``invoke`` emits one plausible
  ``run_sql`` tool callback and returns a fixed grounded answer (no model, no SQL).
- ``app.services.run.get_tracing_callbacks`` -> ``[]`` (no Langfuse phone-home).
- ``app.core.db.run_readonly_query`` / ``count_rows`` -> canned reader output for
  the synchronous ``rerun`` path.
"""

from __future__ import annotations

import time

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.common.settings import settings
from app.core import flags
from app.main import create_app

# The fixed grounded answer every faked agent turn returns (ADR-0006 shape).
FAKE_GROUNDING = {
    "sql": "SELECT COUNT(*) AS total_transactions FROM transactions;",
    "explanation": "There are 1,159,966 transactions in the dataset.",
    "assumptions": ["Counted all rows; no filters applied."],
    "tables_and_joins_used": ["transactions"],
    "flags": [],
}

_TOOL_RUN_ID = "fake-tool-run"
_TOOL_OUT = '{"columns": ["total_transactions"], "rows": [[1159966]], "row_cap": 100, "truncated": false, "flags": []}'


class _FakeGraph:
    """A compiled-graph stand-in: fire one tool callback, return a grounded answer."""

    def invoke(self, state: dict, config: dict) -> dict:
        for handler in (config or {}).get("callbacks", []) or []:
            if hasattr(handler, "on_tool_start"):
                handler.on_tool_start(
                    {"name": "run_sql"},
                    '{"sql": "SELECT COUNT(*) FROM transactions"}',
                    run_id=_TOOL_RUN_ID,
                )
                handler.on_tool_end(_TOOL_OUT, run_id=_TOOL_RUN_ID)
        return {"messages": [], "grounding": dict(FAKE_GROUNDING)}


def _fake_run_readonly_query(sql_text: str) -> flags.Result:
    return flags.Result(
        columns=["total_transactions"], rows=[[1159966]], row_cap=100, truncated=False
    )


@pytest.fixture(autouse=True)
def runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install the LLM/reader/tracing fakes for every test (harmless for pure routes)."""
    monkeypatch.setattr("app.services.run._graph", lambda: _FakeGraph())
    monkeypatch.setattr("app.services.run.get_tracing_callbacks", lambda: [])
    monkeypatch.setattr("app.core.db.run_readonly_query", _fake_run_readonly_query)
    monkeypatch.setattr("app.core.db.count_rows", lambda table: 1159966)


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def db_ok() -> None:
    """Skip the calling test if Postgres is unreachable (DB is a genuine P1 dep)."""
    try:
        con = psycopg.connect(settings.pg_dsn, connect_timeout=3)
        con.close()
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not reachable: {exc}")


def wait_until(predicate, timeout_s: float = 20.0) -> None:
    """Poll ``predicate()`` at 100ms intervals until true or the deadline passes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail(f"wait_until timed out after {timeout_s}s")
