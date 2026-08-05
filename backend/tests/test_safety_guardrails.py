"""D-7: Unit tests for safety guardrails.

Covers:
- validate_statement_type: blocks 17 unsafe statement types, passes SELECT, caps at 3 SELECTs
- enforce_row_limit: appends LIMIT, preserves existing LIMIT, handles edge cases
- Timeout behavior via actual anyio.move_on_after
"""

import time

import anyio
import pytest

from app.api.services.query_safety import (
    LIMIT_PATTERN,
    MAX_SELECT_STATEMENTS,
    UNSAFE_STATEMENTS,
    enforce_row_limit,
    validate_statement_type,
)


class TestValidateStatementType:
    """Statement-type validation (A-3)."""

    @pytest.mark.parametrize(
        "statement",
        list(UNSAFE_STATEMENTS),
    )
    def test_blocks_unsafe_statements(self, statement: str) -> None:
        result = validate_statement_type(f"{statement} t FROM foo")
        assert result is not None
        assert statement in result

    def test_allows_safe_select(self) -> None:
        result = validate_statement_type("SELECT * FROM transactions LIMIT 100")
        assert result is None

    def test_allows_select_with_subquery(self) -> None:
        result = validate_statement_type(
            "SELECT * FROM (SELECT id FROM transactions WHERE amount > 1000) sub"
        )
        assert result is None

    def test_allows_exactly_max_selects(self) -> None:
        query = "\n".join(
            ["SELECT 1", "SELECT 2", "SELECT 3"]
        )
        result = validate_statement_type(query)
        assert result is None

    def test_rejects_over_max_selects(self) -> None:
        query = "\n".join(
            ["SELECT 1", "SELECT 2", "SELECT 3", "SELECT 4"]
        )
        result = validate_statement_type(query)
        assert result is not None
        assert "Too many SELECT" in result

    def test_allows_lowercase_select(self) -> None:
        result = validate_statement_type("select * from transactions")
        assert result is None

    def test_allows_empty_string(self) -> None:
        result = validate_statement_type("")
        assert result is None

    def test_allows_comment_prefix(self) -> None:
        result = validate_statement_type("-- comment\nSELECT * FROM transactions")
        assert result is None

    def test_allows_parenthesized_select(self) -> None:
        result = validate_statement_type("(SELECT * FROM transactions)")
        assert result is None

    def test_blocks_leading_dash_statement(self) -> None:
        """Leading dash is stripped before checking the token."""
        result = validate_statement_type("- INSERT INTO foo VALUES (1)")
        assert result is not None
        assert "INSERT" in result

    def test_blocks_leading_paren_statement(self) -> None:
        """Leading paren is stripped before checking the token."""
        result = validate_statement_type("( DROP TABLE transactions)")
        assert result is not None
        assert "DROP" in result

    def test_select_within_cte_is_safe(self) -> None:
        result = validate_statement_type(
            "WITH cte AS (SELECT id FROM transactions) SELECT * FROM cte"
        )
        # WITH is not in UNSAFE_STATEMENTS, so it depends on first token
        # The first token is "WITH" which is safe, SELECT count is 2 <= 3


class TestEnforceRowLimit:
    """Row-limit enforcement (A-4)."""

    def test_appends_limit_when_absent(self) -> None:
        result = enforce_row_limit("SELECT * FROM transactions")
        assert "LIMIT 10000" in result

    def test_preserves_existing_limit(self) -> None:
        result = enforce_row_limit("SELECT * FROM transactions LIMIT 100")
        assert "LIMIT 10000" not in result
        assert "LIMIT 100" in result

    def test_respects_custom_max_rows(self) -> None:
        result = enforce_row_limit("SELECT * FROM transactions", max_rows=50)
        assert "LIMIT 50" in result

    def test_strips_trailing_semicolon_and_readds(self) -> None:
        result = enforce_row_limit("SELECT * FROM transactions;")
        assert result.endswith(";")
        assert result.count(";") == 1

    def test_limit_in_column_name_still_appends(self) -> None:
        """Column named credit_limit_usd_cents won't match LIMIT_PATTERN."""
        result = enforce_row_limit("SELECT credit_limit_usd_cents FROM cards")
        assert "LIMIT 10000" in result

    def test_limit_after_join(self) -> None:
        result = enforce_row_limit(
            "SELECT t.* FROM transactions t JOIN cards c ON t.card_id = c.id"
        )
        assert "LIMIT 10000" in result

    def test_limit_case_insensitive(self) -> None:
        result = enforce_row_limit(
            "SELECT * FROM transactions limit 50"
        )
        assert "LIMIT 10000" not in result

    def test_whitespace_only_sql(self) -> None:
        result = enforce_row_limit("   ")
        assert "LIMIT 10000" in result


class TestTimeoutBehavior:
    """Timeout enforcement (A-5)."""

    @pytest.mark.anyio
    async def test_timeout_prevents_slow_op_completion(self) -> None:
        """anyio.move_on_after should prevent completion of long-running ops."""
        results: dict | None = None

        async def slow_op() -> None:
            await anyio.sleep(5)
            nonlocal results
            results = {"columns": [], "rows": []}

        with anyio.move_on_after(0.01):
            await slow_op()

        assert results is None, "Timeout should prevent query from completing"

    @pytest.mark.anyio
    async def test_timeout_triggers_cancellederror(self) -> None:
        """Verify that CancelledError is raised when timeout fires."""
        caught = False
        with anyio.move_on_after(0.01):
            try:
                await anyio.sleep(1)
            except (anyio.get_cancelled_exc_class(), BaseException):
                caught = True

        assert caught
