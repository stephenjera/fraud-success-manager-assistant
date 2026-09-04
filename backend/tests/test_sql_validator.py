"""P1 proof — the sqlglot guard admits a single read-only SELECT and rejects everything else.

Pure (no DB, no LLM): ``validate_sql`` is either normalised SQL or a
:class:`~app.core.sql_validator.SqlRejected`. The role (ADR-0007) is the floor;
these pin the first gate the agent's SQL meets (ADR-0002).
"""

from __future__ import annotations

import unittest

from app.core.sql_validator import SqlRejected, primary_table, validate_sql


class AdmitsSelect(unittest.TestCase):
    def test_plain_select(self) -> None:
        """A plain SELECT is admitted and normalised."""
        self.assertIn("SELECT", validate_sql("SELECT * FROM transactions"))

    def test_select_join(self) -> None:
        """A joined SELECT (the fraud_labels ↔ transactions pattern) is admitted."""
        out = validate_sql(
            "SELECT t.id, fl.is_fraud FROM transactions t "
            "JOIN fraud_labels fl ON fl.transaction_id = t.id"
        )
        self.assertIn("JOIN", out.upper())

    def test_cte_select(self) -> None:
        """A CTE-wrapped SELECT is still a single read-only SELECT."""
        out = validate_sql("WITH c AS (SELECT id FROM users) SELECT * FROM c")
        self.assertIn("id", out)

    def test_returns_cleaned_single_statement(self) -> None:
        """The returned SQL has no stray semicolons."""
        self.assertNotIn(";", validate_sql("SELECT 1 FROM (SELECT 1 AS x) v "))


class RejectsWrites(unittest.TestCase):
    def _assert_rejected(self, sql: str) -> None:
        with self.assertRaises(SqlRejected):
            validate_sql(sql)

    def test_empty(self) -> None:
        """Empty / blank SQL is rejected."""
        self._assert_rejected("")
        self._assert_rejected("   ")

    def test_insert(self) -> None:
        """An INSERT is rejected."""
        self._assert_rejected("INSERT INTO users (id) VALUES (1)")

    def test_update(self) -> None:
        """An UPDATE is rejected."""
        self._assert_rejected("UPDATE users SET gender = 'X'")

    def test_delete(self) -> None:
        """A DELETE is rejected."""
        self._assert_rejected("DELETE FROM users")

    def test_drop(self) -> None:
        """A DROP is rejected."""
        self._assert_rejected("DROP TABLE users")

    def test_multi_statement(self) -> None:
        """More than one statement is rejected."""
        self._assert_rejected("SELECT 1; DROP TABLE users")


class PGCatalogPolicy(unittest.TestCase):
    """P3.5 — pg_catalog is allowed by design (chaos report, by design section).

    The reference_readonly role needs pg_catalog for catalog metadata
    (schemas, roles, settings). No password or DSN columns are exposed."""

    def test_pg_roles_allowed(self) -> None:
        """Reading pg_roles is permitted — catalog metadata is safe."""
        out = validate_sql("SELECT rolname FROM pg_roles")
        self.assertIn("pg_roles", out)

    def test_pg_settings_allowed(self) -> None:
        """Reading pg_settings is permitted — non-secret settings are visible."""
        out = validate_sql("SELECT name FROM pg_settings")
        self.assertIn("pg_settings", out)

    def test_current_user_allowed(self) -> None:
        """current_user is a system function, not a catalog table."""
        out = validate_sql("SELECT current_user")
        self.assertIn("CURRENT_USER", out.upper())


class PrimaryTable(unittest.TestCase):
    def test_first_table(self) -> None:
        """Returns the first table a SELECT reads from."""
        self.assertEqual(
            primary_table("SELECT t.a FROM transactions t JOIN users u ON true"),
            "transactions",
        )

    def test_no_table(self) -> None:
        """A literal SELECT has no table to attribute."""
        self.assertIsNone(primary_table("SELECT 1"))


if __name__ == "__main__":
    unittest.main()
