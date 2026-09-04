"""The backtest (spec §8, ADR-0014) — two universes, one join basis, no LLM.

Pure, deterministic: each pass is a single read-only SQL query on the
fixed ADR-0014 basis, with four ``SUM(CASE WHEN …)`` columns returning
the four confusion-matrix cells. The derived metrics (precision/recall/
FPR/baseline_fraud_rate/lift) are Python on top of those four ints.

Universes (ADR-0014):

- ``labeled_only``  — the "clean" pass: only ``fraud_labels``-bearing
  rows are in scope. Denominators use only rows with a known ground
  truth; an unlabeled row cannot inflate precision.
- ``full_universe`` — the "in the wild" pass: every row is scored.
  Unlabeled rows are treated as not-fraud (the operational assumption:
  the engine flags what it flags, and the label just hasn't arrived).

Basis (ADR-0014 — the clause is join-capable; ``fraud_labels`` is
reachable but is never a filter in the clause):

    reference.transactions t
    LEFT JOIN reference.fraud_labels fl ON fl.transaction_id = t.id
    LEFT JOIN reference.cards   c       ON c.id  = t.card_id
    LEFT JOIN reference.merchants m     ON m.id  = t.merchant_id

The ``where_clause`` is supplied by the rule; the clause is re-validated
here as defence-in-depth (the caller is expected to have validated it
already; the reference_readonly role is the floor even if the clause
were invalid, the read-only SELECT can't hurt ``appstate``).

No ``agents/`` import, no LLM, no writes to ``appstate``. The
ADR-0005 wall is the running test in ``tests/test_architecture.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import sql

from app.core import db
from app.core import rules as rule_rules

# The ADR-0014 basis. Column aliases (t, fl, c, m) are what the caller's
# unqualified ``where_clause`` references resolve against.
_BASIS_FROM = (
    "FROM reference.transactions t "
    "LEFT JOIN reference.fraud_labels fl ON fl.transaction_id = t.id "
    "LEFT JOIN reference.cards   c       ON c.id  = t.card_id "
    "LEFT JOIN reference.merchants m     ON m.id  = t.merchant_id"
)

# The four-cell CASE template. {clause} is the caller's clause (already
# validated, spliced via SQL formatting; the role is the floor). The
# universe (who is in scope) is applied as a WHERE on the outer query —
# so one CASE template serves both universes.
_CELLS_TEMPLATE = (
    " SELECT "
    "  SUM(CASE WHEN ({clause}) AND fl.is_fraud = 1 THEN 1 ELSE 0 END) AS tp,"
    "  SUM(CASE WHEN ({clause}) AND (fl.is_fraud = 0 OR fl.transaction_id IS NULL) "
    "           THEN 1 ELSE 0 END) AS fp,"
    "  SUM(CASE WHEN NOT ({clause}) AND fl.is_fraud = 1 THEN 1 ELSE 0 END) AS fn,"
    "  SUM(CASE WHEN NOT ({clause}) AND (fl.is_fraud = 0 OR fl.transaction_id IS NULL) "
    "           THEN 1 ELSE 0 END) AS tn " + _BASIS_FROM
)


@dataclass(frozen=True, slots=True)
class Universe:
    """One side of the two-universe report: the four confusion-matrix cells."""

    tp: int
    fp: int
    fn: int
    tn: int

    # Spec §8 derived metrics, all from the four cells.
    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def false_positive_rate(self) -> float:
        return self.fp / (self.fp + self.tn) if (self.fp + self.tn) else 0.0

    @property
    def baseline_fraud_rate(self) -> float:
        total = self.tp + self.fp + self.fn + self.tn
        return (self.tp + self.fn) / total if total else 0.0

    @property
    def lift(self) -> float:
        baseline = self.baseline_fraud_rate
        return self.precision / baseline if baseline else 0.0

    def as_block(self, name: str) -> dict[str, Any]:
        """The per-universe JSONB block (confusion_matrix + metrics + coverage)."""
        tp, fp, fn, tn = self.tp, self.fp, self.fn, self.tn
        total = tp + fp + fn + tn
        matched = tp + fp
        return {
            "universe": name,
            "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "metrics": {
                "precision": round(self.precision, 6),
                "recall": round(self.recall, 6),
                "false_positive_rate": round(self.false_positive_rate, 6),
                "baseline_fraud_rate": round(self.baseline_fraud_rate, 6),
                "lift": round(self.lift, 6),
            },
            "coverage": {
                "matched_count": matched,
                "total_rows": total,
                "total_fraud": tp + fn,
                "support": matched / total if total else 0.0,
            },
        }


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The full deterministic result of one ``POST /rules/{id}/backtest``."""

    labeled_only: Universe
    full_universe: Universe
    temporal_stability: dict[str, dict[str, float]]
    sample: dict[str, Any]

    def as_dto(self, *, rule_id: str, window: str, where_clause: str) -> dict[str, Any]:
        """The ``BacktestResult`` DTO (api-contract.md Gap C, ADR-0014)."""
        return {
            "rule_id": rule_id,
            "window": window,
            "where_clause": where_clause,
            "labeled_only": self.labeled_only.as_block("labeled_only"),
            "full_universe": self.full_universe.as_block("full_universe"),
            "temporal_stability": self.temporal_stability,
            "sample": self.sample,
        }


def _cells(con: psycopg.Connection, clause: str, *, where: sql.Composable) -> Universe:
    """One universe's four cells in a single pass (CASE template + WHERE)."""
    q = sql.SQL(_CELLS_TEMPLATE).format(clause=sql.SQL(clause)) + where
    row = con.execute(q).fetchone()
    assert row is not None  # the CASE aggregation always returns exactly one row
    tp, fp, fn, tn = (int(x or 0) for x in row)
    return Universe(tp=tp, fp=fp, fn=fn, tn=tn)


def _temporal(con: psycopg.Connection, clause: str) -> dict[str, dict[str, float]]:
    """Earlier/later-half precision & recall (ADR-0014 temporal split).

    The split point is the median ``transactions.date``; it is applied on
    both halves. Only ``labeled_only`` rows are scored (a half without
    ground truth is meaningless for precision/recall), so this block is
    a property of the clean universe, not a per-universe fork.
    """
    # The median's date: the row at offset FLOOR(total/2) in a
    # date-ordered scan of the *labeled* universe.
    total_row = con.execute(
        sql.SQL(
            "SELECT COUNT(*) " + _BASIS_FROM + " WHERE fl.transaction_id IS NOT NULL"
        )
    ).fetchone()
    assert total_row is not None  # COUNT(*) always returns a row
    total = int(total_row[0])
    if not total:
        empty = {"precision": 0.0, "recall": 0.0}
        return {"earlier_slice": empty, "later_slice": empty}

    offset = total // 2
    median_date = con.execute(
        sql.SQL(
            "SELECT t.date "
            + _BASIS_FROM
            + " WHERE fl.transaction_id IS NOT NULL ORDER BY t.date LIMIT 1 OFFSET %s"
        ),
        (offset,),
    ).fetchone()
    if median_date is None or median_date[0] is None:
        empty = {"precision": 0.0, "recall": 0.0}
        return {"earlier_slice": empty, "later_slice": empty}
    bound = median_date[0]

    def _half(op: str) -> dict[str, float]:
        q = sql.SQL(
            " SELECT "
            "  SUM(CASE WHEN ({clause}) AND fl.is_fraud = 1 THEN 1 ELSE 0 END) AS tp,"
            "  SUM(CASE WHEN ({clause}) AND (fl.is_fraud = 0 OR fl.transaction_id IS NULL) "
            "           THEN 1 ELSE 0 END) AS fp,"
            "  SUM(CASE WHEN NOT ({clause}) AND fl.is_fraud = 1 THEN 1 ELSE 0 END) AS fn "
            + _BASIS_FROM
            + " WHERE fl.transaction_id IS NOT NULL AND t.date "
        ).format(clause=sql.SQL(clause)) + sql.SQL(op + " %s")
        row = con.execute(q, (bound,)).fetchone()
        assert row is not None  # the CASE aggregation always returns exactly one row
        tp, fp, fn = (int(x or 0) for x in row)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        return {"precision": round(precision, 6), "recall": round(recall, 6)}

    return {"earlier_slice": _half("<="), "later_slice": _half(">")}


def _sample(con: psycopg.Connection, clause: str, limit: int = 5) -> dict[str, Any]:
    """The five matched rows the FSM eyeballs before approving (Gap C)."""
    q = sql.SQL(
        " SELECT t.id AS transaction_id, t.date AS txn_date, "
        "  t.amount_usd_cents / 100.0 AS amount_usd, "
        "  c.card_type, c.card_brand, "
        "  COALESCE(m.name, 'UNKNOWN') AS merchant_name "
        + _BASIS_FROM
        + " WHERE ({clause}) ORDER BY t.id DESC LIMIT %s"
    ).format(clause=sql.SQL(clause))
    cur = con.execute(q, (limit,))
    cols = [d.name for d in (cur.description or [])]
    rows = [[_json_cell(v) for v in r] for r in cur]
    return {"count": len(rows), "columns": cols, "rows": rows}


def _json_cell(value: Any) -> Any:
    """Make a row cell JSON-serialisable (Decimal → float, date/datetime → ISO)."""
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def run(
    *,
    rule_id: str,
    clause: str,
    window: str = "full",
) -> BacktestResult:
    """Compute the full report; deterministic, no LLM, no writes.

    Args:
        rule_id: The rule this backtest is for (FK on the stored row).
        clause: The rule's current ``where_clause`` (re-validated here
            as defence-in-depth).
        window: ``"full"`` or ``"custom"`` (DTO's top-level field).

    Returns:
        A :class:`BacktestResult` — two universe blocks
        (``confusion_matrix + metrics + coverage`` each), the temporal
        stability block, and the shared five-row sample.

    Raises:
        rule_rules.InvalidWhereClause: For an empty, unparseable,
            out-of-basis, or subquery clause.
        psycopg.OperationalError: If the reference data is unreachable.
    """
    canonical = rule_rules.validate_where_clause(clause)
    con = db._connect()  # noqa: SLF001 — reuse db's reference_readonly reader
    try:
        labeled_only = _cells(
            con,
            canonical,
            where=sql.SQL(" WHERE fl.transaction_id IS NOT NULL"),
        )
        full_universe = _cells(
            con,
            canonical,
            where=sql.SQL(""),
        )
        temporal = _temporal(con, canonical)
        sample = _sample(con, canonical)
    finally:
        con.close()
    return BacktestResult(
        labeled_only=labeled_only,
        full_universe=full_universe,
        temporal_stability=temporal,
        sample=sample,
    )


__all__ = ["BacktestResult", "Universe", "run"]
