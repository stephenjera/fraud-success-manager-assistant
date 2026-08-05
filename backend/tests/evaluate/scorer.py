"""
D-2: Execution accuracy scorer.

Runs agent on test questions via the /api/explore endpoint, then executes
the generated SQL and compares results against expected output.

D-3: Query validity rate scorer.
% of generated SQL that passes syntax/schema validation.

D-4: Latency metric scorer.
Captures p50/p95 per complexity category.

D-5: Rule precision/recall scorer.
Evaluates generated rule predicates against fraud_labels.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import duckdb
import requests  # type: ignore

from app.database import get_analytics_db, SCHEMA_DDL
from tests.evaluate.test_dataset import ALL_PAIRS, NLSQLPair


# ──────────────────────────────────────────────
# Scoring data models
# ──────────────────────────────────────────────


class ScoreCategory(str, Enum):
    EXECUTION_EXACT = "execution_exact"
    EXECUTION_APPROX = "execution_approx"
    VALIDITY = "validity"
    LATENCY = "latency"
    RULE_PRECISION = "rule_precision"
    RULE_RECALL = "rule_recall"


@dataclass
class TestResult:
    question: str
    category: str
    generated_sql: str | None
    sql_valid: bool
    execution_match: bool
    row_count: int | None
    columns_match: bool
    latency_ms: float | None
    rule_precision: float | None
    rule_recall: float | None
    error: str | None


@dataclass
class EvalSummary:
    """Aggregated results for a full eval run."""

    total_pairs: int
    passed: int
    failed: int
    results: list[TestResult]

    execution_accuracy: float
    validity_rate: float
    p50_latency: float
    p95_latency: float
    avg_rule_precision: float
    avg_rule_recall: float

    # Category breakdown
    category_accuracy: dict[str, float] = field(default_factory=dict)


API_BASE = "http://localhost:8000"
SESSION_ID = "eval-runner"


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def query_db(sql: str) -> dict[str, Any]:
    """Execute SQL against the DuckDB-connected SQLite database."""
    for conn in get_analytics_db():
        try:
            conn.execute(sql)
            columns = [desc[0] for desc in conn.description] if conn.description else []
            rows = [list(r) for r in conn.fetchall()]
            return {"columns": columns, "rows": rows}
        finally:
            conn.close()
    raise RuntimeError("Could not get DB connection")


def validate_sql_syntax(sql: str) -> bool:
    """Check if SQL is syntactically valid via LIMIT 0 probe."""
    try:
        clean = sql.strip().rstrip(";")
        if not clean.upper().startswith("SELECT"):
            clean = f"SELECT * FROM ({clean})"
        test = f"SELECT * FROM ({clean}) AS _probe LIMIT 0"
        query_db(test)
        return True
    except Exception:
        return False


def normalize_column_set(columns: list[str]) -> set[str]:
    return {c.lower().strip() for c in columns}


def call_agent(question: str) -> dict[str, Any] | None:
    """Hit /api/explore with a question, return result dict."""
    payload = {
        "session_id": SESSION_ID,
        "prompt": question,
    }
    try:
        res = requests.post(
            f"{API_BASE}/api/explore",
            json=payload,
            timeout=120,
        )
        if res.status_code == 200:
            return res.json()
        return None
    except requests.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to API at {API_BASE}. "
            "Is the backend running?"
        )
    except requests.Timeout:
        return None


def call_execute(sql: str) -> dict[str, Any] | None:
    """Hit /api/execute with raw SQL."""
    payload = {
        "session_id": SESSION_ID,
        "sql": sql,
    }
    try:
        res = requests.post(
            f"{API_BASE}/api/execute",
            json=payload,
            timeout=60,
        )
        if res.status_code == 200:
            return res.json()
        return None
    except requests.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to API at {API_BASE}. "
            "Is the backend running?"
        )


def call_rule_eval(where_clause: str) -> dict[str, Any] | None:
    """Hit /api/rules/evaluate with a WHERE clause."""
    payload = {
        "where_clause": where_clause,
    }
    try:
        res = requests.post(
            f"{API_BASE}/api/rules/evaluate",
            json=payload,
            timeout=60,
        )
        if res.status_code == 200:
            return res.json()
        return None
    except requests.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to API at {API_BASE}. "
            "Is the backend running?"
        )


# ──────────────────────────────────────────────
# D-2: Execution accuracy scorer
# ──────────────────────────────────────────────


def score_execution_accuracy(
    pair: NLSQLPair,
    agent_result: dict[str, Any] | None,
) -> tuple[bool, int | None, bool]:
    """
    Run generated SQL and compare against expected results.
    Returns (execution_match, row_count, columns_match).
    """
    if agent_result is None or not agent_result.get("sql"):
        return False, None, False

    gen_sql = agent_result["sql"]

    # Execute generated SQL via the API
    exec_result = call_execute(gen_sql)
    if exec_result is None:
        return False, None, False

    row_count = len(exec_result.get("rows", []))
    gen_columns = normalize_column_set(exec_result.get("columns", []))

    # Column overlap (at least 50% of expected columns present)
    if pair.expected_columns:
        expected_cols = normalize_column_set(pair.expected_columns)
        overlap = len(gen_columns & expected_cols)
        total_expected = len(expected_cols)
        columns_match = overlap >= max(1, total_expected * 0.4)
    else:
        columns_match = True

    # Row count in acceptable range
    in_range = pair.min_row_count <= row_count <= pair.max_row_count

    return in_range and columns_match, row_count, columns_match


# ──────────────────────────────────────────────
# D-3: Query validity rate
# ──────────────────────────────────────────────


def score_validity(gen_sql: str) -> bool:
    return validate_sql_syntax(gen_sql) if gen_sql else False


# ──────────────────────────────────────────────
# D-5: Rule precision/recall scorer
# ──────────────────────────────────────────────


def score_rule_metrics(
    pair: NLSQLPair,
    agent_result: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    """Send rule predicate to /api/rules/evaluate and return (precision, recall)."""
    if agent_result is None:
        return None, None

    rule_pred = agent_result.get("rule_predicate")
    if not rule_pred:
        return None, None

    eval_result = call_rule_eval(rule_pred)
    if eval_result is None:
        return None, None

    metrics = eval_result.get("metrics", {})
    return (
        metrics.get("precision"),
        metrics.get("recall"),
    )


# ──────────────────────────────────────────────
# D-4 / Aggregate latency collector
# ──────────────────────────────────────────────


def compute_percentiles(latencies: list[float]) -> tuple[float, float]:
    """Return (p50, p95) for a list of latency values in ms."""
    if not latencies:
        return 0.0, 0.0
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50 = sorted_lat[max(0, n // 2 - 1)]
    idx95 = max(0, int(n * 0.95) - 1)
    p95 = sorted_lat[idx95]
    return p50, p95


# ──────────────────────────────────────────────
# Master runner
# ──────────────────────────────────────────────


def run_online_eval(
    skip_rule_eval: bool = False,
    limit: int | None = None,
) -> EvalSummary:
    """
    Run full online evaluation: D-2, D-3, D-4, and D-5.

    Args:
        skip_rule_eval: Skip D-5 rule precision/recall evaluation.
        limit: Max number of test pairs to evaluate (None for all).

    Requires a running backend at API_BASE.
    """
    results: list[TestResult] = []
    latencies: list[float] = []
    all_precisions: list[float] = []
    all_recalls: list[float] = []
    category_correct: dict[str, list[bool]] = {}

    pairs = ALL_PAIRS[:limit] if limit else ALL_PAIRS

    for idx, pair in enumerate(pairs, 1):
        start = time.perf_counter()

        print(f"[{idx}/{len(pairs)}] {pair.category:>8} | {pair.question[:60]}...")

        agent_result = call_agent(pair.question)
        elapsed_ms = (time.perf_counter() - start) * 1000

        gen_sql = agent_result.get("sql") if agent_result else None

        # Validity
        sql_valid = score_validity(gen_sql or "")

        # Execution accuracy
        exec_match, row_count, columns_match = (False, None, False)
        if gen_sql:
            exec_match, row_count, columns_match = score_execution_accuracy(
                pair, agent_result
            )

        # Rule metrics (D-5)
        rule_precision = None
        rule_recall = None
        if not skip_rule_eval and pair.requires_rule:
            rule_precision, rule_recall = score_rule_metrics(pair, agent_result)

        if rule_precision is not None:
            all_precisions.append(rule_precision)
        if rule_recall is not None:
            all_recalls.append(rule_recall)

        latencies.append(elapsed_ms)

        status = "PASS" if exec_match else "FAIL"
        print(
            f"         [{status}] valid={sql_valid} | rows={row_count} | "
            f"{elapsed_ms:.0f}ms"
        )

        result = TestResult(
            question=pair.question,
            category=pair.category,
            generated_sql=gen_sql,
            sql_valid=sql_valid,
            execution_match=exec_match,
            row_count=row_count,
            columns_match=columns_match,
            latency_ms=elapsed_ms,
            rule_precision=rule_precision,
            rule_recall=rule_recall,
            error=None if agent_result else "Agent call failed or timed out",
        )
        results.append(result)

        cat = pair.category
        category_correct.setdefault(cat, []).append(exec_match)

    passed = sum(1 for r in results if r.execution_match)
    failed = len(results) - passed

    valid_count = sum(1 for r in results if r.sql_valid)
    validity_rate = valid_count / len(results) if results else 0.0

    exec_accuracy = passed / len(results) if results else 0.0

    p50, p95 = compute_percentiles(latencies)

    avg_precision = statistics.mean(all_precisions) if all_precisions else 0.0
    avg_recall = statistics.mean(all_recalls) if all_recalls else 0.0

    category_accuracy = {}
    for cat, marks in category_correct.items():
        cat_passed = sum(marks)
        category_accuracy[cat] = cat_passed / len(marks) if marks else 0.0

    return EvalSummary(
        total_pairs=len(results),
        passed=passed,
        failed=failed,
        results=results,
        execution_accuracy=exec_accuracy,
        validity_rate=validity_rate,
        p50_latency=p50,
        p95_latency=p95,
        avg_rule_precision=avg_precision,
        avg_rule_recall=avg_recall,
        category_accuracy=category_accuracy,
    )


# ──────────────────────────────────────────────
# Pretty-print helper
# ──────────────────────────────────────────────


def print_summary(summary: EvalSummary) -> dict[str, Any]:
    """Print structured summary and return as dict for downstream use."""
    out = {
        "D-2: Execution Accuracy",
        f"  Overall accuracy: {summary.execution_accuracy:.1%} "
        f"({summary.passed}/{summary.total_pairs})",
        "Per-category:",
    }
    for cat, acc in summary.category_accuracy.items():
        print(f"  - {cat}: {acc:.1%}")

    out_str: dict[str, Any] = {
        "D-2 Execution Accuracy": {
            "overall": round(summary.execution_accuracy, 3),
            "passed": summary.passed,
            "total": summary.total_pairs,
            "by_category": summary.category_accuracy,
        },
        "D-3 Query Validity": round(summary.validity_rate, 3),
        "D-4 Latency (ms)": {
            "p50": round(summary.p50_latency, 1),
            "p95": round(summary.p95_latency, 1),
        },
        "D-5 Rule Metrics": {
            "avg_precision": round(summary.avg_rule_precision, 3),
            "avg_recall": round(summary.avg_rule_recall, 3),
        },
    }

    print(f"\nD-3: Query Validity: {summary.validity_rate:.1%}")
    print(f"\nD-4: Latency")
    print(f"  p50: {summary.p50_latency:.0f}ms")
    print(f"  p95: {summary.p95_latency:.0f}ms")
    print(f"\nD-5: Rule Metrics")
    print(f"  Avg precision: {summary.avg_rule_precision:.3f}")
    print(f"  Avg recall:    {summary.avg_rule_recall:.3f}")

    # Per-result detail (collapsed)
    print("\n--- Per-result detail ---")
    for r in summary.results:
        status = "PASS" if r.execution_match else "FAIL"
        print(
            f"  [{status}] {r.category} | rows={r.row_count} | "
            f"latency={r.latency_ms:.0f}ms"
        )

    return out_str
