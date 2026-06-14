def build_execution_context(grid_response: dict) -> dict:
    """
    Converts execution results into LLM-usable decision context.
    """

    rows = grid_response.get("rows", [])
    columns = grid_response.get("columns", [])

    if not rows:
        return {
            "signal_summary": "NO_DATA",
            "top_signal": None,
            "decision_candidates": [],
        }

    # assume first column = feature, second = fraud_count, third = rate
    signals = []

    for row in rows:
        signals.append(
            {
                "feature": row[0],
                "fraud_count": row[1] if len(row) > 1 else 0,
                "fraud_rate": row[2] if len(row) > 2 else 0,
            }
        )

    # sort by fraud_count (important signal)
    signals_sorted = sorted(signals, key=lambda x: x["fraud_count"], reverse=True)

    top = signals_sorted[0]

    # build decision candidates (THIS is what LLM should use)
    decision_candidates = [
        {
            "rule_hint": f"t.errors = '{s['feature']}'",
            "strength": s["fraud_count"],
        }
        for s in signals_sorted[:5]
        if s["feature"] is not None
    ]

    return {
        "signal_summary": {
            "total_signals": len(signals_sorted),
            "top_feature": top["feature"],
            "top_fraud_count": top["fraud_count"],
        },
        "top_signal": top,
        "decision_candidates": decision_candidates,
        "raw_signals": signals_sorted[:10],
    }
