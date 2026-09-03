"""The rule state machine (spec §7, ``architecture/rule-lifecycle.md``).

Pure logic: a fixed ``verb → {from_status → to_status}`` table. ``core/`` holds
it so the FSM ``deploy``-from-``draft`` is a raised :class:`RuleIllegalTransition`
(a clean ``409 RULE_ILLEGAL_TRANSITION`` at the API edge), not a silent no-op.
Nothing here touches ``agents/`` (the ADR-0005 wall) or the DB; the API layer
translates the exception into the contract's error shape.

    draft ──► backtested ──► approved ──► deployed
                     │
                     └────► rejected            (terminal)

``deploy`` is the only exit from ``approved``; ``rejected`` never comes back.
"""

from __future__ import annotations

# The rule's five statuses (mirrors the ``rules.status`` CHECK).
DRAFT = "draft"
BACKTESTED = "backtested"
APPROVED = "approved"
DEPLOYED = "deployed"
REJECTED = "rejected"

STATUSES = frozenset({DRAFT, BACKTESTED, APPROVED, DEPLOYED, REJECTED})

# verb → { from_status → to_status }. A verb is legal only from a listed status;
# any other current status is an illegal transition (rule-lifecycle.md).
_TRANSITIONS: dict[str, dict[str, str]] = {
    "backtest": {DRAFT: BACKTESTED, BACKTESTED: BACKTESTED},  # re-backtest self-loops
    "approve": {BACKTESTED: APPROVED},
    "reject": {BACKTESTED: REJECTED},
    "deploy": {APPROVED: DEPLOYED},
    "disable": {DEPLOYED: DEPLOYED},  # a flag, not a status change
}

TERMINAL = frozenset({REJECTED})


class RuleIllegalTransition(Exception):
    """The FSM refused a verb from the rule's current status.

    Carries a stable ``code`` (``RULE_ILLEGAL_TRANSITION``) so the API edge
    can surface the frozen error shape without this module knowing about ``api/``.
    """

    code = "RULE_ILLEGAL_TRANSITION"

    def __init__(self, verb: str, current: str) -> None:
        message = f"Rule verb '{verb}' is not allowed from status '{current}'."
        super().__init__(message)
        self.verb = verb
        self.current = current


def can_transition(current: str, verb: str) -> bool:
    """Whether ``verb`` is legal from ``current`` (the idempotency precheck)."""
    return current in _TRANSITIONS.get(verb, {})


def apply(current: str, verb: str) -> str:
    """Return the status a rule is in after ``verb``; reject an illegal one.

    Args:
        current: The rule's current ``status``.
        verb: One of ``backtest|approve|reject|deploy|disable``.

    Returns:
        The new ``status``.

    Raises:
        RuleIllegalTransition: If the verb is unknown or illegal from ``current``.
    """
    targets = _TRANSITIONS.get(verb)
    if targets is None:
        raise RuleIllegalTransition(verb, current)
    target = targets.get(current)
    if target is None:
        raise RuleIllegalTransition(verb, current)
    return target


def where_clause_editable(has_backtest_row: bool) -> bool:
    """The freeze line (``rule-lifecycle.md``): a ``PATCH where_clause`` is legal
    only while no ``backtest_results`` row exists against the clause.

    A failed backtest writes no row, so it does not freeze. ``title`` is always
    editable and never goes through this gate.
    """
    return not has_backtest_row
