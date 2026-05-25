import re

from app.core.logger import get_logger

logger = get_logger(__name__)


FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
}


class SQLValidationError(Exception):
    """Raised when SQL is unsafe or invalid."""


def validate_sql(sql: str) -> str:
    """Validate SQL query for safety."""
    logger.info("Validating SQL")

    cleaned = sql.strip().upper()

    # 1. Must start with SELECT
    if not cleaned.startswith("SELECT"):
        raise SQLValidationError("Only SELECT queries are allowed")

    # 2. No multiple statements
    if ";" in cleaned[:-1]:
        raise SQLValidationError("Multiple SQL statements are not allowed")

    # 3. No forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in cleaned:
            raise SQLValidationError(f"Forbidden keyword detected: {keyword}")

    logger.info("SQL validation passed")

    return sql
