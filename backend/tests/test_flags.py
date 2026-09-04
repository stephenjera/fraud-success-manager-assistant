"""P1 proof — the deterministic sanity flags (ADR-0006 ``flags`` on the grounding).

Flags are a property of the *result set*, computed here, not reported by the LLM.
So they are assertable against a known result — the whole point of ADR-0006.
"""

from __future__ import annotations

import unittest

from app.core import flags


def _result(
    rows: list[list[object]], truncated: bool = False, cap: int = flags.row_cap()
) -> flags.Result:
    return flags.Result(columns=["a"], rows=rows, row_cap=cap, truncated=truncated)


class FlagSet(unittest.TestCase):
    def test_empty(self) -> None:
        """No rows → exactly ``empty_result``."""
        self.assertEqual(flags.run(_result([])), ["empty_result"])

    def test_row_cap_hit(self) -> None:
        """Truncated result → ``row_cap_hit``."""
        self.assertIn(
            "row_cap_hit", flags.run(_result([[1]] * flags.row_cap(), truncated=True))
        )

    def test_large_result(self) -> None:
        """A big fraction (>5%) of a large table → ``large_result``."""
        self.assertIn("large_result", flags.run(_result([[1]] * 100), total_rows=2000))

    def test_clean(self) -> None:
        """A small sample of an even larger table → no flags."""
        self.assertEqual(flags.run(_result([[1], [2]]), total_rows=1_000_000), [])

    def test_to_dict_shape(self) -> None:
        """The rerun-body envelope carries exactly the four result fields."""
        got = _result([[1]]).to_dict()
        self.assertEqual(set(got), {"columns", "rows", "row_cap", "truncated"})


if __name__ == "__main__":
    unittest.main()
