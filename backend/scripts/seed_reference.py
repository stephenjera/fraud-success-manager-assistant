"""Seed the ``reference`` schema from the dev SQLite dataset.

Runs as the superuser (the read-only role cannot write ``reference`` — ADR-0007).
Owns the ``reference`` schema end-to-end (ADR-0015): it creates the reference
tables if absent (idempotent ``CREATE ... IF NOT EXISTS``), grants SELECT to
``reference_readonly``, then TRUNCATE + COPY per table (idempotent re-seed).
Alembic owns only the ``appstate`` tables; ``db-init/001-roles.sql`` and
``db-init/002-schemas.sql`` own the two roles and the two schema objects. The
~100 MB
dataset streams through a file-like that emits Postgres ``COPY ... FORMAT text``
— tab-separated, ``\\N`` for NULL, backslash-escaped ``\\ t n r`` — so it never
fully lands in memory.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import psycopg

from app.common.settings import settings

_BACKEND = Path(__file__).resolve().parent.parent
_SQLITE = _BACKEND / "data" / "data.db"

# Column order + Postgres types. The SQLite file is the data source of truth;
# its declared types (`BOOLEAN`, `DATETIME`, `REAL`) are loose, so the Postgres
# shape is pinned here. Two deliberate casts, documented in data-model.md:
#   - fraud_labels.transaction_id -> BIGINT (data is all-numeric; lets the
#     ground-truth `transaction_id = transactions.id` join type-match)
#   - fraud_labels.is_fraud       -> INTEGER (the P2 backtest does SUM(is_fraud);
#     documented `INTEGER (0/1)`, not BOOLEAN)
_DDL: dict[str, str] = {
    "users": (
        "CREATE TABLE IF NOT EXISTS reference.users ("
        "id BIGINT PRIMARY KEY, birth_date DATE, gender TEXT, address TEXT,"
        "latitude DOUBLE PRECISION, longitude DOUBLE PRECISION,"
        "per_capita_income_usd_cents BIGINT, yearly_income_usd_cents BIGINT,"
        "total_debt_usd_cents BIGINT, credit_score INTEGER);"
    ),
    "cards": (
        "CREATE TABLE IF NOT EXISTS reference.cards ("
        "id BIGINT PRIMARY KEY, user_id BIGINT, card_brand TEXT, card_type TEXT,"
        "expires DATE, has_chip BOOLEAN, credit_limit_usd_cents BIGINT,"
        "acct_open_date DATE, year_pin_last_changed INTEGER, card_on_dark_web BOOLEAN);"
    ),
    "fraud_labels": (
        "CREATE TABLE IF NOT EXISTS reference.fraud_labels ("
        "transaction_id BIGINT PRIMARY KEY, is_fraud INTEGER);"
    ),
    "mcc_codes": (
        "CREATE TABLE IF NOT EXISTS reference.mcc_codes ("
        "mcc INTEGER PRIMARY KEY, description TEXT);"
    ),
    "merchants": (
        "CREATE TABLE IF NOT EXISTS reference.merchants ("
        "id BIGINT PRIMARY KEY, name TEXT, mcc INTEGER);"
    ),
    "merchant_locations": (
        "CREATE TABLE IF NOT EXISTS reference.merchant_locations ("
        "id BIGINT PRIMARY KEY, merchant_id BIGINT, city TEXT, state TEXT, zip INTEGER);"
    ),
    "transactions": (
        "CREATE TABLE IF NOT EXISTS reference.transactions ("
        "id BIGINT PRIMARY KEY, date TIMESTAMP, card_id BIGINT, amount_usd_cents BIGINT,"
        "transaction_type TEXT, merchant_id BIGINT, merchant_location_id BIGINT, errors TEXT);"
    ),
}


def _columns(table: str) -> list[str]:
    """Column order for a reference table, from the SQLite file."""
    con = sqlite3.connect(f"file:{_SQLITE}?mode=ro", uri=True)
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    finally:
        con.close()


def _copy_cell(cell: object) -> bytes:
    """Postgres ``COPY TEXT`` escaping for a single cell."""
    if cell is None:
        return b"\\N"
    if isinstance(cell, bool):
        return b"t" if cell else b"f"
    if isinstance(cell, (int, float)):
        return str(cell).encode("utf-8")
    out = bytearray()
    for ch in str(cell):
        if ch == "\\":
            out += b"\\\\"
        elif ch == "\t":
            out += b"\\t"
        elif ch == "\n":
            out += b"\\n"
        elif ch == "\r":
            out += b"\\r"
        else:
            out += ch.encode("utf-8", errors="replace")
    return bytes(out)


def seed() -> dict[str, int]:
    """Create the reference tables, then TRUNCATE + COPY each from SQLite."""
    sqlite = sqlite3.connect(f"file:{_SQLITE}?mode=ro", uri=True)
    con = psycopg.connect(settings.pg_dsn, autocommit=True)
    try:
        with con.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS reference;")
            for ddl in _DDL.values():
                cur.execute(ddl)
            # The seed owns the reference schema: after creating the tables, grant the
            # read-only role SELECT on them (ADR-0007 / ADR-0015). Idempotent — re-granting
            # an existing grant is harmless, and this makes `psql -f` repair a broken grant
            # without a fresh volume.
            cur.execute("GRANT USAGE ON SCHEMA reference TO reference_readonly;")
            cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA reference TO reference_readonly;")
            for table in _DDL:
                cur.execute(f"TRUNCATE reference.{table} RESTART IDENTITY")
    except Exception:
        con.close()
        sqlite.close()
        raise
    counts: dict[str, int] = {}
    try:
        for table in _DDL:
            cols = _columns(table)
            src = sqlite.cursor()
            src.execute(f"SELECT {', '.join(cols)} FROM {table}")
            with con.cursor() as cur:
                with cur.copy(
                    f"COPY reference.{table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT text)"
                ) as cp:
                    for row in src:
                        cp.write(b"\t".join(_copy_cell(c) for c in row) + b"\n")
            n = sqlite.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            counts[table] = n
            print(f"  {table:<20} {n:>12,} rows", flush=True)
    finally:
        con.close()
        sqlite.close()
    return counts


def main() -> None:
    print("seeding reference schema from data/data.db…", flush=True)
    counts = seed()
    print(f"seeded {sum(counts.values()):,} rows across {len(counts)} tables.")


if __name__ == "__main__":
    main()
