import os
import requests

BASE_URL = os.getenv("API_URL", "http://localhost:8000")


def build_execution_context(grid):
    """
    Lightweight test-side context builder (mirrors backend logic).
    Keeps test deterministic and independent.
    """

    signals = []

    for row in grid.get("rows", []):
        if not row:
            continue

        feature = row[0]

        # skip null/noise
        if feature is None:
            continue

        signals.append(
            {
                "feature_value": feature,
                "fraud_count": row[1] if len(row) > 1 else 0,
                "fraud_rate": row[2] if len(row) > 2 else None,
            }
        )

    if not signals:
        return {
            "signals": [],
            "top_signal": None,
        }

    # sort by strength
    signals = sorted(signals, key=lambda x: x["fraud_count"], reverse=True)

    return {
        "signals": signals[:5],  # TOP-K ONLY
        "top_signal": signals[0],
    }


def test_fsm_full_loop():
    session_id = "fsm-test-session-001"

    # =====================================================
    # TURN 1 — EXPLORE
    # =====================================================
    res_1 = requests.post(
        f"{BASE_URL}/api/explore",
        json={
            "session_id": session_id,
            "prompt": "What is the most common cause of fraud?",
        },
    )

    assert res_1.status_code == 200, res_1.text
    data_1 = res_1.json()

    sql_1 = data_1["sql"]
    assert sql_1 and "SELECT" in sql_1.upper()

    print("\n[TURN 1 SQL]\n", sql_1)

    # =====================================================
    # TURN 2 — EXECUTE
    # =====================================================
    exec_1 = requests.post(
        f"{BASE_URL}/api/execute",
        json={
            "session_id": session_id,
            "sql": sql_1,
        },
    )

    assert exec_1.status_code == 200, exec_1.text
    grid_1 = exec_1.json()

    print("\n[TURN 2 RESULTS]")
    print("columns:", grid_1["columns"])
    print("sample rows:", grid_1["rows"][:3])

    # =====================================================
    # BUILD EXECUTION CONTEXT (FIXED + CLEAN)
    # =====================================================
    execution_context = build_execution_context(grid_1)

    print("\n[EXECUTION CONTEXT]")
    print(execution_context)

    # =====================================================
    # TURN 3 — RULE SYNTHESIS (GROUNDED)
    # =====================================================
    res_2 = requests.post(
        f"{BASE_URL}/api/explore",
        json={
            "session_id": session_id,
            "prompt": (
                "Convert the discovered fraud pattern into a production rule. "
                "Return a WHERE clause only."
            ),
            "execution_context": execution_context,
        },
    )

    assert res_2.status_code == 200, res_2.text
    data_2 = res_2.json()

    rule = data_2.get("rule_predicate") or ""

    assert rule, "No rule predicate generated"

    # 🚨 hard guard against hallucination placeholders
    assert "<" not in rule
    assert "TOP" not in rule

    print("\n[TURN 3 RULE]\n", rule)

    # =====================================================
    # TURN 4 — RULE EVALUATION
    # =====================================================
    eval_res = requests.post(
        f"{BASE_URL}/api/rules/evaluate",
        json={
            "where_clause": rule,
        },
    )

    assert eval_res.status_code == 200, eval_res.text

    metrics = eval_res.json()["metrics"]

    print("\n[TURN 4 METRICS]")
    print("TP:", metrics["true_positives"])
    print("FP:", metrics["false_positives"])
    print("FN:", metrics["false_negatives"])
    print("Precision:", metrics["precision"])
    print("Recall:", metrics["recall"])
    print("Net Value:", metrics["net_value"])

    # =====================================================
    # TURN 5 — VALIDATION
    # =====================================================
    assert metrics["true_positives"] >= 0
    assert metrics["precision"] >= 0.0

    assert (
        metrics["precision"] > 0.1 or metrics["true_positives"] > 0
    ), "Rule has no signal — FSM failed to extract meaningful pattern"

    print("\n--- FSM LOOP TEST PASSED ---")
