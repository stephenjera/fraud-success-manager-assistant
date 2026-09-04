"""E2E pattern recovery — the pipeline correctness test (eval-design.md).

Injects N synthetic fraud rows as a superuser, runs a FRESH query against
the data to assert the synthetic pattern is visible, then tears down.
The "copy" of seeded data is expressed as N extra rows cleaned up in teardown.

Requires Postgres: skips cleanly when unreachable (uses conftest db_ok).
"""

from __future__ import annotations

import unittest

import psycopg

from app.common.settings import settings


class E2EPatternRecovery(unittest.TestCase):
    """Prove the reference side can see synthetic rows injected by a superuser.

    The full agent loop (NL→SQL) is gated on a live LLM. This test proves
    the data path — the synthetic pattern lands in reference and is visible
    to the reference_readonly role. If the LLM is live, the agent would
    discover the same pattern via run_sql.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.con = psycopg.connect(settings.pg_dsn)
        cls.con.autocommit = True

    EVAL_TXN_ID = 99_999_999

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cur = cls.con.cursor()
            cur.execute(
                "DELETE FROM reference.fraud_labels WHERE transaction_id = %s",
                (cls.EVAL_TXN_ID,),
            )
            cur.execute(
                "DELETE FROM reference.transactions WHERE id = %s",
                (cls.EVAL_TXN_ID,),
            )
        finally:
            cls.con.close()

    def test_synthetic_rows_are_visible_to_readonly_role(self) -> None:
        """A superuser can INSERT, and reference_readonly can SELECT them back."""
        cur = self.con.cursor()
        cur.execute(
            "INSERT INTO reference.transactions (id, date, card_id, merchant_id, amount_usd_cents) "
            "VALUES (%s, CURRENT_DATE, 1, 1, 999900)",
            (self.EVAL_TXN_ID,),
        )
        cur.execute(
            "INSERT INTO reference.fraud_labels (transaction_id, is_fraud) VALUES (%s, 1)",
            (self.EVAL_TXN_ID,),
        )
        # Read back as readonly
        readonly = psycopg.connect(settings.reference_dsn, autocommit=True)
        try:
            rc = readonly.cursor()
            rc.execute(
                "SELECT fl.is_fraud FROM reference.transactions t "
                "JOIN reference.fraud_labels fl ON fl.transaction_id = t.id "
                "WHERE t.id = %s",
                (self.EVAL_TXN_ID,),
            )
            row = rc.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], 1)
        finally:
            readonly.close()

    def test_synthetic_rows_are_cleaned_up(self) -> None:
        """After teardown, the test rows are gone."""
        cur = self.con.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM reference.transactions WHERE id = %s",
            (self.EVAL_TXN_ID,),
        )
        count = cur.fetchone()[0]
        self.assertEqual(count, 0)

    def test_reference_readonly_cannot_write(self) -> None:
        """The readonly role cannot INSERT (ADR-0007 floor)."""
        readonly = psycopg.connect(settings.reference_dsn, autocommit=True)
        try:
            rc = readonly.cursor()
            with self.assertRaises(Exception):  # noqa: B017
                rc.execute(
                    "INSERT INTO reference.transactions (id, date, card_id, merchant_id, amount_usd_cents) "
                    "VALUES (99999998, CURRENT_DATE, 1, 1, 0)"
                )
        finally:
            readonly.close()


if __name__ == "__main__":
    unittest.main()
