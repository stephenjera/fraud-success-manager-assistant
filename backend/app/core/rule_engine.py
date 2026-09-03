"""Rule-engine mock (spec §9): the concrete ``RuleEngineClient`` in v1.

Only ``services/`` may call this — the agent has no import path here
(ADR-0005 wall, asserted by ``tests/test_architecture.py``). The swap
to a real engine is "replace :class:`MockRuleEngineClient` in
:func:`client`" and no caller changes.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol


class RuleEngineClient(Protocol):  # pragma: no cover - spec §9 protocol
    """The spec §9 rule-engine interface the FSM sees."""

    def deploy_rule(self, payload: dict[str, Any]) -> str:
        """Ship the payload; return the engine's external rule ID."""
        raise NotImplementedError

    def get_rule_status(self, external_rule_id: str) -> dict[str, Any]:
        """Status record for a deployed external rule."""
        raise NotImplementedError

    def disable_rule(self, external_rule_id: str) -> dict[str, Any]:
        """Flip the (mock) rule off; return the new status record."""
        raise NotImplementedError


class MockRuleEngineClient:
    """In-process mock (spec §9): fake external ID, no engine state.

    The durable record of any deploy is the ``deployment_records`` row
    (data-model.md) — the mock just returns the external ID the row stores.
    """

    def deploy_rule(self, payload: dict[str, Any]) -> str:
        # ponytail: deterministic fake ids ("mock-rule-<hex>") so tests can
        # assert exact equality; a real client returns its own opaque id.
        return "mock-rule-" + uuid.uuid4().hex[:12]

    def get_rule_status(self, external_rule_id: str) -> dict[str, Any]:
        return {"external_rule_id": external_rule_id, "status": "active"}

    def disable_rule(self, external_rule_id: str) -> dict[str, Any]:
        return {"external_rule_id": external_rule_id, "status": "disabled"}


_default = MockRuleEngineClient()


def client() -> MockRuleEngineClient:
    """The active rule-engine client — swap here, never at the call site."""
    return _default


__all__ = [
    "RuleEngineClient",
    "MockRuleEngineClient",
    "client",
]
