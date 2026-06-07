"""Deterministic high-speed query engine running analytical backtests inside DuckDB."""

from typing import Any

import duckdb


def execute_raw_sql(conn: duckdb.DuckDBPyConnection, sql_query: str) -> dict[str, Any]:
    """Execute a validated query string against the database and construct a clean grid.

    Args:
        conn: Current active read-only DuckDB connection proxy.
        sql_query: The target SELECT query string to execute.

    Returns:
        A dictionary payload holding column names, rows, and timing stats.
    """
    clean_sql = sql_query.strip().rstrip(";")

    # Use DuckDB's cursor description to grab column string headers instantly
    cursor = conn.execute(clean_sql)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()

    return {
        "columns": columns,
        "rows": rows,
    }


def run_backtest(conn: duckdb.DuckDBPyConnection, where_clause: str) -> dict[str, Any]:
    """Evaluate a proposed fraud rule fragment against all historical datasets.

    Args:
        conn: Current active read-only DuckDB connection proxy.
        where_clause: Isolated sql filter logic text string.

    Returns:
        Structured metrics detailing blocked ratios and chronological chart series.
    """
    # Explicitly alias tables to match the instructions provided to the AI agent
    base_query_structure = f"""
        FROM transactions t
        LEFT JOIN fraud_labels fl ON t.id = fl.transaction_id
        LEFT JOIN cards c ON t.card_id = c.id
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN merchants m ON t.merchant_id = m.id
        LEFT JOIN mcc_codes mc ON m.mcc = mc.mcc
        WHERE {where_clause.strip().rstrip(";")}
    """

    # 1. Calculate top-line summary KPI blocks using matching aliases
    metrics_sql = f"""
        SELECT 
            COUNT(*) as total_blocked,
            CAST(COUNT(*) FILTER (WHERE fl.is_fraud = TRUE) AS INTEGER) as true_positives,
            CAST(COUNT(*) FILTER (WHERE fl.is_fraud = FALSE OR fl.is_fraud IS NULL) AS INTEGER) as false_positives,
            CAST(COALESCE(SUM(CASE WHEN fl.is_fraud = TRUE THEN t.amount_usd_cents ELSE 0 END), 0) AS REAL) / 100.0 as total_fraud_value_saved_usd
        {base_query_structure}
    """
    metrics_res = conn.execute(metrics_sql).fetchone()

    total_blocked = metrics_res[0] if metrics_res else 0
    true_positives = metrics_res[1] if metrics_res else 0
    false_positives = metrics_res[2] if metrics_res else 0
    saved_usd = metrics_res[3] if metrics_res else 0.0

    fp_ratio = false_positives / total_blocked if total_blocked > 0 else 0.0

    # 2. Extract trend telemetry arrays for the Recharts timeline canvas using matching aliases
    timeline_sql = f"""
        SELECT 
            CAST(t.date AS DATE) as block_date,
            CAST(COUNT(*) FILTER (WHERE fl.is_fraud = TRUE) AS INTEGER) as fraud_blocked,
            CAST(COUNT(*) FILTER (WHERE fl.is_fraud = FALSE OR fl.is_fraud IS NULL) AS INTEGER) as legitimate_blocked
        {base_query_structure}
        GROUP BY block_date
        ORDER BY block_date ASC
    """
    timeline_rows = conn.execute(timeline_sql).fetchall()

    timeline_series = [
        {"date": str(row[0]), "fraud_blocked": row[1], "legitimate_blocked": row[2]}
        for row in timeline_rows
    ]

    return {
        "metrics": {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_positive_ratio": fp_ratio,
            "total_fraud_value_saved_usd": saved_usd,
        },
        "timeline_series": timeline_series,
    }
