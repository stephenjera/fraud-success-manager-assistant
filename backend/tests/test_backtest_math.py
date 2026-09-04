"""Unit tests for the backtest Universe math — pure, no DB, no LLM.

The four-cell → derived metrics computation is deterministic Python on top
of ints.  These tests assert correctness of precision, recall, FPR, baseline
fraud rate, lift, and the per-universe JSON block shape.
"""

from __future__ import annotations

import unittest

from app.core.backtest import Universe


class MetricsTest(unittest.TestCase):
    """Correctness of the five derived metrics from four cells."""

    def test_perfect_classifier(self) -> None:
        u = Universe(tp=100, fp=0, fn=0, tn=900)
        self.assertEqual(u.precision, 1.0)
        self.assertEqual(u.recall, 1.0)
        self.assertEqual(u.false_positive_rate, 0.0)
        self.assertEqual(u.baseline_fraud_rate, 0.1)
        self.assertEqual(u.lift, 10.0)

    def test_zeros_are_division_safe(self) -> None:
        u = Universe(tp=0, fp=0, fn=0, tn=0)
        self.assertEqual(u.precision, 0.0)
        self.assertEqual(u.recall, 0.0)
        self.assertEqual(u.false_positive_rate, 0.0)
        self.assertEqual(u.baseline_fraud_rate, 0.0)
        self.assertEqual(u.lift, 0.0)

    def test_no_false_positives_division_by_zero(self) -> None:
        u = Universe(tp=50, fp=0, fn=50, tn=0)
        self.assertEqual(u.precision, 1.0)
        self.assertEqual(u.false_positive_rate, 0.0)

    def test_no_fraud_at_all(self) -> None:
        u = Universe(tp=0, fp=10, fn=0, tn=990)
        self.assertEqual(u.precision, 0.0)
        self.assertEqual(u.recall, 0.0)
        self.assertEqual(u.baseline_fraud_rate, 0.0)
        self.assertEqual(u.lift, 0.0)

    def test_baseline_and_lift(self) -> None:
        u = Universe(tp=30, fp=70, fn=20, tn=880)
        self.assertAlmostEqual(u.baseline_fraud_rate, 0.05)
        prec = 30 / 100
        self.assertAlmostEqual(u.lift, prec / 0.05)


class AsBlockTest(unittest.TestCase):
    """The JSONB block shape matches the DTO contract (ADR-0014)."""

    def test_block_keys(self) -> None:
        u = Universe(tp=10, fp=5, fn=2, tn=83)
        block = u.as_block("labeled_only")
        self.assertIn("universe", block)
        self.assertIn("confusion_matrix", block)
        self.assertIn("metrics", block)
        self.assertIn("coverage", block)

    def test_confusion_matrix_values(self) -> None:
        u = Universe(tp=10, fp=5, fn=2, tn=83)
        cm = u.as_block("x")["confusion_matrix"]
        self.assertEqual(cm, {"tp": 10, "fp": 5, "fn": 2, "tn": 83})

    def test_coverage_values(self) -> None:
        u = Universe(tp=10, fp=5, fn=2, tn=83)
        cov = u.as_block("x")["coverage"]
        self.assertEqual(cov["matched_count"], 15)
        self.assertEqual(cov["total_rows"], 100)
        self.assertEqual(cov["total_fraud"], 12)

    def test_support_is_fraction(self) -> None:
        u = Universe(tp=10, fp=5, fn=2, tn=83)
        self.assertAlmostEqual(u.as_block("x")["coverage"]["support"], 0.15)

    def test_zero_total_support_is_zero(self) -> None:
        u = Universe(tp=0, fp=0, fn=0, tn=0)
        self.assertEqual(u.as_block("x")["coverage"]["support"], 0.0)


if __name__ == "__main__":
    unittest.main()
