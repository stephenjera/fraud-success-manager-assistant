"""A4: a rule clause must never reference the fraud label (finding #13)."""

import unittest
import warnings

warnings.filterwarnings("ignore", message=".*uvloop.*")

from app.core import rules


class LabelGateTests(unittest.TestCase):
    def test_label_only_clause_rejected(self) -> None:
        with self.assertRaises(rules.InvalidWhereClause):
            rules.validate_where_clause("fl.is_fraud = 1")

    def test_label_and_behavior_clause_rejected(self) -> None:
        with self.assertRaises(rules.InvalidWhereClause):
            rules.validate_where_clause(
                "fl.is_fraud = 1 AND amount_usd_cents > 100000"
            )

    def test_plain_behavior_clause_still_allowed(self) -> None:
        clause = rules.validate_where_clause("amount_usd_cents > 100000")
        assert "amount_usd_cents" in clause

    def test_gate_error_names_the_column(self) -> None:
        with self.assertRaises(rules.InvalidWhereClause) as ctx:
            rules.validate_where_clause("fl.is_fraud = 1")
        self.assertIn("is_fraud", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
