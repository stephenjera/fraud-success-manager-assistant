from app.db.connection import Database
from app.db.executor import SQLExecutor


def evaluate_rule(rule_where: str) -> dict:
    """Evaluate a rule by returning simple stats (count matched rows).

    Returns a dict with `matched_count` and an example SQL used.
    """
    db = Database()
    executor = SQLExecutor(db)

    sql = f"SELECT COUNT(*) as matched_count FROM transactions WHERE {rule_where}"

    results, _ = executor.execute(sql)

    matched = results[0].get("matched_count") if results else 0

    return {"matched_count": matched, "sql": sql}
