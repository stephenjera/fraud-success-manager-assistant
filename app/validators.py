import logging

from sql_executor import run_query

logger = logging.getLogger(__name__)


def validate_sql(sql: str) -> tuple[bool, str]:
    logger.debug("Validating SQL: %s", sql.strip().replace('\n', ' ')[:300])
    sql_lower = sql.lower()

    # Must be SELECT
    if not sql_lower.strip().startswith("select"):
        logger.warning("SQL validation failed: not a SELECT")
        return False, "Only SELECT queries are allowed"

    # Block dangerous keywords
    forbidden = ["drop", "delete", "update", "insert", "alter", ";"]
    if any(word in sql_lower for word in forbidden):
        logger.warning("SQL validation failed: forbidden keyword present")
        return False, "Forbidden SQL operation detected"

    # Must reference fraud_labels
    if "fraud_labels" not in sql_lower:
        logger.warning("SQL validation failed: missing fraud_labels")
        return False, "Query must include fraud_labels"

    # Must include join condition
    if (
        "transactions.id" not in sql_lower
        or "fraud_labels.transaction_id" not in sql_lower
    ):
        logger.warning("SQL validation failed: missing join condition")
        return False, "Missing required join condition"

    logger.debug("SQL validation passed")
    return True, ""


def validate_sql_execution(sql: str) -> tuple[bool, str]:
    logger.debug("Validating SQL execution for: %s", sql.strip().replace('\n', ' ')[:300])
    try:
        run_query(f"EXPLAIN QUERY PLAN {sql}")
        return True, ""
    except Exception as e:
        logger.warning("SQL execution validation failed: %s", e)
        return False, str(e)
