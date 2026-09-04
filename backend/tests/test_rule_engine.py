"""Unit tests for the rule-engine mock (spec §9) — pure, no DB, no LLM.

The mock returns deterministic fake IDs and stable status records.
Tests assert the interface contract: deploy returns a string matching
the pattern, status returns active, disable returns disabled.
"""

from __future__ import annotations

import unittest

from app.core.rule_engine import MockRuleEngineClient, client


class DeployTest(unittest.TestCase):
    def test_returns_string(self) -> None:
        c = MockRuleEngineClient()
        eid = c.deploy_rule({})
        self.assertIsInstance(eid, str)

    def test_id_starts_with_mock_rule(self) -> None:
        c = MockRuleEngineClient()
        eid = c.deploy_rule({"rule_id": "x", "payload": {}})
        self.assertTrue(eid.startswith("mock-rule-"))

    def test_ids_are_unique(self) -> None:
        c = MockRuleEngineClient()
        ids = {c.deploy_rule({}) for _ in range(10)}
        self.assertEqual(len(ids), 10)


class StatusTest(unittest.TestCase):
    def test_active_on_deploy(self) -> None:
        c = MockRuleEngineClient()
        eid = c.deploy_rule({})
        status = c.get_rule_status(eid)
        self.assertEqual(status["status"], "active")
        self.assertEqual(status["external_rule_id"], eid)

    def test_disabled_after_disable(self) -> None:
        c = MockRuleEngineClient()
        eid = c.deploy_rule({})
        status = c.disable_rule(eid)
        self.assertEqual(status["status"], "disabled")
        self.assertEqual(status["external_rule_id"], eid)


class ClientSingletonTest(unittest.TestCase):
    def test_returns_same_instance(self) -> None:
        self.assertIs(client(), client())


if __name__ == "__main__":
    unittest.main()
