from typing import Any
from app.core.logger import get_logger
from app.db.connection import Database
from app.db.executor import SQLExecutor

logger = get_logger(__name__)


def calculate_rule_telemetry(where_clause: str) -> dict[str, Any]:
    """
    Computes exact math performance metrics for a standalone SQL WHERE condition
    by resolving matching transaction vectors natively against the database engine.
    """
    logger.info("Computing deterministic precision/recall math variables")
    db = Database()
    executor = SQLExecutor(db)

    # Clean up empty or missing clauses safely
    if not where_clause or not where_clause.strip():
        where_clause = "1=1"

    # 1. Evaluate total system-wide baseline metrics
    global_sql = """
    SELECT 
        COUNT(*) as total_tx,
        SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) as total_fraud
    FROM transactions t
    LEFT JOIN fraud_labels f ON t.id = f.transaction_id
    """

    try:
        global_res, _ = executor.execute(global_sql)
        total_transactions = global_res[0]["total_tx"] or 0
        total_fraud = global_res[0]["total_fraud"] or 0
    except Exception as err:
        logger.error(f"Failed to fetch global validation base statistics: {err}")
        return {
            "precision": 0.0,
            "recall": 0.0,
            "block_rate": 0.0,
            "flagged_total": 0,
            "status": "REJECTED",
            "warnings": ["Database baseline fetch failure"],
        }

    if total_transactions == 0:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "block_rate": 0.0,
            "flagged_total": 0,
            "status": "ACCEPTED",
            "warnings": ["Empty transaction ledger system"],
        }

    # 2. Inject rule criteria cleanly into analytical counting queries.
    # We prefix table targets to avoid ambiguous column name errors during joins.
    flagged_sql = f"""
    SELECT 
        COUNT(*) as flagged_total,
        SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) as true_positives
    FROM transactions t
    LEFT JOIN fraud_labels f ON t.id = f.transaction_id
    LEFT JOIN cards c ON t.card_id = c.id
    LEFT JOIN users u ON t.user_id = u.id
    WHERE {where_clause}
    """

    try:
        flagged_res, _ = executor.execute(flagged_sql)
        flagged_total = flagged_res[0]["flagged_total"] or 0
        true_positives = flagged_res[0]["true_positives"] or 0
    except Exception as err:
        logger.error(
            f"Rule evaluation syntax error with WHERE clause [{where_clause}]: {err}"
        )
        return {
            "precision": 0.0,
            "recall": 0.0,
            "block_rate": 0.0,
            "flagged_total": 0,
            "status": "REJECTED",
            "warnings": [f"Invalid rule logical syntax: {str(err)}"],
        }

    # 3. Perform Exact Telemetry Formulations
    precision = true_positives / flagged_total if flagged_total > 0 else 0.0
    recall = true_positives / total_fraud if total_fraud > 0 else 0.0
    block_rate = flagged_total / total_transactions if total_transactions > 0 else 0.0

    # 4. Evaluate Business Threshold Guardrails
    warnings = []
    status = "ACCEPTED"

    if flagged_total < 15:
        warnings.append("Low statistical sample size — risky validation bounds.")

    if precision < 0.15:
        warnings.append("Severe False Positives — rule violates quality threshold.")
        status = "REJECTED"
    elif precision < 0.45:
        warnings.append(
            "Moderate False Positives — alignment verification recommended."
        )
        status = "REVIEW"

    if block_rate > 0.15:
        warnings.append(
            "High Customer Impact — rule intercepts large operational volume."
        )
        status = "REVIEW"

    telemetry = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "block_rate": round(block_rate, 4),
        "flagged_total": flagged_total,
        "status": status,
        "warnings": warnings,
    }

    logger.info("Computed telemetry: %s", telemetry)
    return telemetry
