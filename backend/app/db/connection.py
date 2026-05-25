import sqlite3
from pathlib import Path

from app.core.logger import get_logger

logger = get_logger(__name__)

DATABASE_PATH = Path(__file__).parent.parent / "data" / "data.db"


class Database:
    """SQLite database wrapper with read-only safety and non-blocking parameters."""

    def __init__(self, db_path: Path = DATABASE_PATH) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        """Create a thread-safe read-only connection that won't deadlock telemetry pools."""
        # FIX: Append a timeout parameter (in milliseconds) and enable shared cache pool explicitly
        # to ensure multiple rapid read-only telemetry queries don't step on each other's toes.
        uri = f"file:{self.db_path.as_posix()}?mode=ro&timeout=15000&cache=shared"

        logger.info(
            "Opening non-blocking read-only database connection: %s", self.db_path
        )

        try:
            return sqlite3.connect(
                uri,
                uri=True,
                check_same_thread=False,  # Crucial for multi-threaded FastAPI background tasks
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to open database connection: %s", exc)
            raise
