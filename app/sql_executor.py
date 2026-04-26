import logging

from database import get_connection

logger = logging.getLogger(__name__)


def run_query(sql: str):
    logger.info("Executing SQL query: %s", sql.strip().replace('\n', ' ')[:400])
    conn = get_connection()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        logger.info("Query returned %d rows", len(rows))
        return [dict(row) for row in rows]
    except Exception:
        logger.exception("Error executing SQL")
        raise
    finally:
        conn.close()
