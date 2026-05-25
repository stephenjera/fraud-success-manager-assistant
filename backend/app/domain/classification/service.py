def classify_query(question: str) -> str:
    """Very small heuristic classifier for query types.

    Returns one of: 'read', 'analysis', 'unknown'.
    """
    q = question.strip().lower()
    if q.startswith("select") or "select" in q:
        return "read"
    if "insight" in q or "explain" in q:
        return "analysis"
    return "unknown"
