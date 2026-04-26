import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_PATH = Path(__file__).parent.parent
DB_PATH = ROOT_PATH / "data" / "data.db"


def get_connection() -> sqlite3.Connection:
    logger.debug("Opening DB connection to %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
