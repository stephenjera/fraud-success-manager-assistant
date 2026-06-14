import re
from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import (
    RuleEvaluationRequest,
    RuleEvaluationResponse,
    RuleMetrics,
)
from app.database import get_analytics_db
from app.logger import get_logger

router = APIRouter()
logger = get_logger("rules")


@router.post("/evaluate")
def evaluate_rule(
    payload: RuleEvaluationRequest,
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> RuleEvaluationResponse:
    where_clause = payload.where_clause.strip()

    if not where_clause:
        raise HTTPException(status_code=400, detail="where_clause is required")

    condition = re.sub(r"^\s*WHERE\s+", "", where_clause, flags=re.IGNORECASE)

    query = f"""
    WITH evaluated AS (
        SELECT
            t.id AS transaction_id,
            fl.is_fraud,

            CASE
                WHEN {condition} THEN 1
                ELSE 0
            END AS flagged

        FROM transactions t
        LEFT JOIN fraud_labels fl ON t.id = fl.transaction_id
        LEFT JOIN cards c ON t.card_id = c.id
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN merchants m ON t.merchant_id = m.id
        LEFT JOIN mcc_codes mc ON m.mcc = mc.mcc
    ),

    metrics AS (
        SELECT
            SUM(CASE WHEN is_fraud = 1 AND flagged = 1 THEN 1 ELSE 0 END) AS tp,
            SUM(CASE WHEN is_fraud = 0 AND flagged = 1 THEN 1 ELSE 0 END) AS fp,
            SUM(CASE WHEN is_fraud = 1 AND flagged = 0 THEN 1 ELSE 0 END) AS fn,
            SUM(CASE WHEN is_fraud = 0 AND flagged = 0 THEN 1 ELSE 0 END) AS tn
        FROM evaluated
    )

    SELECT * FROM metrics;
    """

    try:
        tp, fp, fn, tn = db.execute(query).fetchone()

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0

        fraud_value = 500
        fp_cost = 50

        return RuleEvaluationResponse(
            metrics=RuleMetrics(
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                true_negatives=tn,
                precision=round(precision, 4),
                recall=round(recall, 4),
                false_positive_rate=round(fpr, 4),
                fraud_value_caught=tp * fraud_value,
                legit_value_blocked=fp * fp_cost,
                net_value=(tp * fraud_value) - (fp * fp_cost),
            )
        )

    except Exception as exc:
        logger.exception("Rule evaluation failed")
        raise HTTPException(
            status_code=400,
            detail=f"Rule evaluation failed: {str(exc)}",
        )
