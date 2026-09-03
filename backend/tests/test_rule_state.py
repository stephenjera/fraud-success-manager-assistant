"""Unit tests for the rule state machine (ADR-0005 clean: pure logic, no LLM, no DB).

The frozen contract (spec §7, ``rule-lifecycle.md``) reduced to a
``verb → {from → to}`` table. What the machine must never do: a verb from a
status it isn't listed for. What it must do: every legal edge in the diagram,
and nothing else.
"""

from __future__ import annotations

import unittest

from app.core import rule_state


class ApplyTest(unittest.TestCase):
    """The legal edges: the diagram, exactly."""

    def test_backtest_moves_draft_to_backtested(self) -> None:
        self.assertEqual(rule_state.apply("draft", "backtest"), "backtested")

    def test_backtest_self_loops_when_already_backtested(self) -> None:
        self.assertEqual(rule_state.apply("backtested", "backtest"), "backtested")

    def test_approve_requires_backtested(self) -> None:
        self.assertEqual(rule_state.apply("backtested", "approve"), "approved")

    def test_reject_requires_backtested(self) -> None:
        self.assertEqual(rule_state.apply("backtested", "reject"), "rejected")

    def test_deploy_requires_approved(self) -> None:
        self.assertEqual(rule_state.apply("approved", "deploy"), "deployed")

    def test_disable_is_a_flag_not_a_status_change(self) -> None:
        self.assertEqual(rule_state.apply("deployed", "disable"), "deployed")

    def test_unknown_verb_raises(self) -> None:
        with self.assertRaises(rule_state.RuleIllegalTransition):
            rule_state.apply("draft", "quantum")


class IllegalTest(unittest.TestCase):
    """Every verb from every *other* status must raise."""

    def _assert_illegal(self, current: str, verb: str) -> None:
        with self.assertRaises(rule_state.RuleIllegalTransition) as ctx:
            rule_state.apply(current, verb)
        exc = ctx.exception
        self.assertEqual(exc.verb, verb)
        self.assertEqual(exc.current, current)
        self.assertEqual(exc.code, "RULE_ILLEGAL_TRANSITION")
        self.assertIn(verb, str(exc))

    def test_approve_not_from_draft(self) -> None:
        self._assert_illegal("draft", "approve")

    def test_deploy_not_from_draft_or_approved(self) -> None:
        self._assert_illegal("draft", "deploy")
        self._assert_illegal("backtested", "deploy")

    def test_reject_not_from_draft_or_approved_or_deployed(self) -> None:
        self._assert_illegal("draft", "reject")
        self._assert_illegal("approved", "reject")
        self._assert_illegal("deployed", "reject")

    def test_backtest_not_from_approved(self) -> None:
        self._assert_illegal("approved", "backtest")

    def test_rejected_is_terminal(self) -> None:
        for verb in ("backtest", "approve", "reject", "deploy", "disable"):
            self._assert_illegal("rejected", verb)

    def test_deployed_has_no_exit(self) -> None:
        for verb in ("backtest", "approve", "reject", "deploy"):
            self._assert_illegal("deployed", verb)


class FreezeLineTest(unittest.TestCase):
    """The PATCH gate: a WHERE edit is legal only while no backtest row exists."""

    def test_editable_before_any_backtest(self) -> None:
        self.assertTrue(rule_state.where_clause_editable(has_backtest_row=False))

    def test_frozen_after_a_backtest_row(self) -> None:
        self.assertFalse(rule_state.where_clause_editable(has_backtest_row=True))


class TableTest(unittest.TestCase):
    """Sanity on the constants a frontend / test may compare against."""

    def test_statuses_match_the_diagram(self) -> None:
        self.assertEqual(
            rule_state.STATUSES,
            frozenset({"draft", "backtested", "approved", "deployed", "rejected"}),
        )

    def test_rejected_is_the_only_terminal(self) -> None:
        self.assertEqual(rule_state.TERMINAL, frozenset({"rejected"}))

    def test_can_transition_is_the_precheck(self) -> None:
        self.assertTrue(rule_state.can_transition("backtested", "approve"))
        self.assertFalse(rule_state.can_transition("draft", "approve"))


if __name__ == "__main__":
    unittest.main()
