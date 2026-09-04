"""Compare the agent's SQL result set against the reference SQL.

Result-set equality, not string match (eval-design.md §10.1). Both run as
``reference_readonly`` against the seeded ``reference`` schema; the comparison
is row-multiset equality with floats rounded, so column ordering, aliases, and
whitespace cannot cause a false negative.
"""

from collections import Counter

import psycopg

_DSN = "postgresql://reference_readonly:reference_readonly@localhost:5433/fraud"
_OPTS = "-csearch_path=reference"


def _norm(v):
    return round(v, 6) if isinstance(v, float) else v


def _canon(row):
    # Order-insensitive within a row: the agent may emit `type,count` where the
    # reference emits `count,type`. Sort each row's values so both sides agree.
    return tuple(
        sorted((_norm(v) for v in row), key=lambda v: (type(v).__name__, str(v)))
    )


def _rows(sql):
    con = psycopg.connect(_DSN, options=_OPTS)
    try:
        cur = con.cursor()
        cur.execute(sql)
        return [_canon(row) for row in cur]
    finally:
        con.close()


def get_assert(output, context):
    vars_ = context.get("vars", {}) or {}
    ref_sql = vars_.get("reference_sql")
    meta = (context.get("providerResponse") or {}).get("metadata", {}) or {}
    agent_sql = meta.get("sql")
    if not agent_sql:
        return {"pass": False, "score": 0, "reason": "agent produced no SQL"}
    if not ref_sql:
        return {"pass": False, "score": 0, "reason": "test case has no reference_sql"}
    try:
        agent = Counter(tuple(r) for r in _rows(agent_sql))
        ref = Counter(tuple(r) for r in _rows(ref_sql))
    except Exception as exc:  # noqa: BLE001 - execution failure is a test failure
        return {"pass": False, "score": 0, "reason": f"failed to execute: {exc}"}
    if agent == ref:
        return {"pass": True, "score": 1, "reason": "result sets match"}
    return {
        "pass": False,
        "score": 0,
        "reason": (f"result set mismatch: agent={list(agent)[:3]} ref={list(ref)[:3]}"),
    }
