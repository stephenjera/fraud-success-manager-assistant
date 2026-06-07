"""Database utility layer connecting DuckDB to the underlying SQLite database."""

from collections.abc import Generator
from pathlib import Path

import duckdb

DATABASE_FOLDER = Path(__file__).parent / "data"
DATABASE_PATH = DATABASE_FOLDER / "data.db"
SCHEMA_DDL_PATH = DATABASE_FOLDER / "schema.sql"


def get_analytics_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Provide a sandboxed, read-only DuckDB connection attached to the SQLite data.

    Yields:
        An active, isolated DuckDB connection pool instance.
    """
    # Connect to an in-memory DuckDB instance to ensure maximum workspace sandbox isolation
    conn = duckdb.connect(":memory:")

    # Install and load the SQLite extension to pull data directly from the file
    conn.execute("INSTALL sqlite;")
    conn.execute("LOAD sqlite;")

    # Attach the provided SQLite database file as a read-only source
    conn.execute(f"ATTACH '{DATABASE_PATH}' AS raw_data (TYPE SQLITE, READ_ONLY TRUE);")

    # Set the search path so queries look at our attached SQLite data by default
    conn.execute("USE raw_data;")

    try:
        yield conn
    finally:
        conn.close()


# Embedded, cleaned DDL definition to feed explicitly into the LLM context window
with Path.open(SCHEMA_DDL_PATH, "r") as f:
    SCHEMA_DDL = f.read()
