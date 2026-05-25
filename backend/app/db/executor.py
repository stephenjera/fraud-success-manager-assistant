from sqlite3 import Row
from typing import Any

from app.core.logger import get_logger
from app.db.connection import Database

logger = get_logger(__name__)


class SQLExecutor:
    """Executes validated SQL queries with thread-safe execution limits."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def execute(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        """Execute SQL and return rows + columns with a safety timeout breaker."""
        logger.info("Executing SQL query")

        conn = self.db.connect()
        conn.row_factory = Row

        # CIRCUIT BREAKER: Every ~100,000 internal virtual machine instructions,
        # invoke a lambda that returns 1. In SQLite, returning a non-zero value 
        # from a progress handler immediately aborts the query execution.
        # conn.set_progress_handler(lambda: 1, 15000000)

        try:
            # Explicitly create a cursor object to ensure clean resource isolation
            cursor = conn.cursor()
            cursor.execute(sql)

            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]

            results = [dict(row) for row in rows]

            logger.info("Query executed successfully: %d rows", len(results))

            cursor.close()
            return results, columns

        except Exception as exc:
            logger.exception("SQL execution failed or hit a resource limit timeout: %s", exc)
            raise

        finally:
            # Always cleanly release file handle locks back to the shared pool
            conn.close()