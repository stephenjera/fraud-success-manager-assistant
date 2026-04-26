import logging

from sql_executor import run_query

logger = logging.getLogger(__name__)


def compute_baseline():
    """
    Compute overall fraud baseline across all transactions.
    """
    logger.info("Computing baseline fraud metrics")

    sql = """
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN f.is_fraud THEN 1 ELSE 0 END) as fraud_count
    FROM transactions t
    JOIN fraud_labels f ON t.id = f.transaction_id
    """

    result = run_query(sql)[0]

    total = result["total"]
    fraud_count = result["fraud_count"] or 0

    fraud_rate = fraud_count / total if total else 0

    logger.info(
        f"Baseline computed: total={total}, fraud_count={fraud_count}, fraud_rate={fraud_rate:.4f}"
    )

    return {
        "total": total,
        "fraud_count": fraud_count,
        "fraud_rate": fraud_rate,
    }


def enrich_results_with_metrics(results: list[dict], baseline: dict):
    """
    Add fraud rate and lift vs baseline to each result row.
    """
    logger.info("Enriching results with fraud metrics")

    baseline_rate = baseline["fraud_rate"]
    enriched = []

    for row in results:
        count = row.get("count", 0)
        fraud_count = row.get("fraud_count", 0) or 0

        fraud_rate = fraud_count / count if count else 0
        lift = fraud_rate / baseline_rate if baseline_rate > 0 else 0

        enriched_row = {
            **row,
            "fraud_rate": fraud_rate,
            "lift_vs_baseline": lift,
        }

        logger.debug(
            f"Row enriched: count={count}, fraud_count={fraud_count}, "
            f"fraud_rate={fraud_rate:.4f}, lift={lift:.2f}"
        )

        enriched.append(enriched_row)

    return enriched


def derive_insight_from_results(results: list[dict], baseline: dict):
    """
    Create deterministic, data-grounded insight.
    """
    logger.info("Deriving insight from results")

    if not results:
        logger.warning("No results available for insight generation")
        return "No suspicious patterns found."

    top_row = results[0]

    transaction_type = top_row.get("transaction_type", "Unknown segment")
    fraud_rate = top_row.get("fraud_rate", 0)
    baseline_rate = baseline["fraud_rate"]
    lift = top_row.get("lift_vs_baseline", 0)

    logger.info(
        f"Top segment: {transaction_type}, fraud_rate={fraud_rate:.4f}, "
        f"baseline={baseline_rate:.4f}, lift={lift:.2f}"
    )

    if fraud_rate > baseline_rate:
        insight = (
            f"{transaction_type} has elevated fraud risk "
            f"({fraud_rate:.2%} fraud rate, {lift:.2f}x baseline)"
        )
    else:
        insight = (
            f"{transaction_type} has lower fraud risk ({fraud_rate:.2%} fraud rate)"
        )

    logger.info(f"Insight derived: {insight}")

    return insight


def evaluate_rule(where_clause: str):
    """
    Evaluate fraud rule quality.
    """
    logger.info(f"Evaluating rule: {where_clause}")

    flagged_sql = f"""
    SELECT
        COUNT(*) as flagged_total,
        SUM(CASE WHEN f.is_fraud THEN 1 ELSE 0 END) as flagged_fraud
    FROM transactions t
    JOIN fraud_labels f ON t.id = f.transaction_id
    WHERE {where_clause}
    """

    flagged = run_query(flagged_sql)[0]

    global_sql = """
    SELECT
        COUNT(*) as total_transactions,
        SUM(CASE WHEN f.is_fraud THEN 1 ELSE 0 END) as total_fraud
    FROM transactions t
    JOIN fraud_labels f ON t.id = f.transaction_id
    """

    global_stats = run_query(global_sql)[0]

    true_positive = flagged["flagged_fraud"] or 0
    flagged_total = flagged["flagged_total"] or 0

    false_positive = flagged_total - true_positive
    total_fraud = global_stats["total_fraud"] or 0
    total_transactions = global_stats["total_transactions"]

    precision = true_positive / flagged_total if flagged_total > 0 else 0
    recall = true_positive / total_fraud if total_fraud > 0 else 0
    block_rate = flagged_total / total_transactions if total_transactions > 0 else 0

    logger.info(
        f"Rule metrics: precision={precision:.4f}, recall={recall:.4f}, block_rate={block_rate:.4f}"
    )

    return {
        "precision": precision,
        "recall": recall,
        "block_rate": block_rate,
        "flagged_total": flagged_total,
        "flagged_fraud": true_positive,
    }


def evaluate_rule_with_checks(where_clause: str):
    """
    Add business-level warnings and acceptance logic.
    """
    result = evaluate_rule(where_clause)

    warnings = []
    status = "ACCEPTED"

    if result["flagged_total"] < 50:
        warnings.append("Low sample size")

    if result["precision"] < 0.10:
        warnings.append("Very low precision — severe false positives")
        status = "REJECTED"

    elif result["precision"] < 0.50:
        warnings.append("Low precision — many false positives")
        status = "REVIEW"

    if result["block_rate"] > 0.30:
        warnings.append("High customer impact — rule blocks large volume")
        status = "REVIEW"

    logger.info(f"Rule warnings: {warnings}")
    logger.info(f"Final rule status: {status}")

    result["warnings"] = warnings
    result["status"] = status

    return result
