"""The readonly reader enforces a statement timeout (spec §11.1).

``db._connect()`` must hand back a connection whose ``statement_timeout`` is
the configured value, and a statement that runs too long must be cancelled
by Postgres (not run to completion). Skips cleanly when Postgres is
unreachable, like the other DB tests (see the ``db_ok`` fixture).
"""

import psycopg
import pytest

import app.core.db as db
from app.common.settings import settings


def test_connection_has_configured_statement_timeout(db_ok: None) -> None:
    con = db._connect()
    try:
        timeout = con.execute("SHOW statement_timeout").fetchone()
    finally:
        con.close()
    ms = settings.readonly_statement_timeout_ms
    assert timeout is not None
    # Postgres renders sub-minute values with units (5000 -> "5s").
    assert timeout[0] in (str(ms), f"{ms // 1000}s")


def test_slow_statement_is_cancelled(
    db_ok: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "readonly_statement_timeout_ms", 200)
    con = db._connect()
    try:
        con.execute("SELECT pg_sleep(3)")
        raise AssertionError("pg_sleep(3) was not cancelled by statement_timeout")
    except psycopg.errors.QueryCanceled:
        pass
    finally:
        con.close()
