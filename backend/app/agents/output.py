"""ADR-0006 typed grounding — the ADR-0006 object the API emits, and the model's output type.

The model writes ``explanation``, ``assumptions``, and ``tables_and_joins_used``.
``structured_output`` (in :mod:`app.agents.graph`) injects the two facts —
``sql`` and ``flags`` — read from the transcript and :mod:`app.core.flags`.

P5 extension: the model can optionally fill ``rule_proposal`` when the answer
describes a detectable pattern. The clause is a *proposal*; ``core/rules``
validates it before it becomes a rule row (ADR-0005 wall unchanged).
``Grounding.sql`` is now nullable — a terminal turn need not have run a query
(e.g. "the data can't answer" or a synthesis from prior results).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuleProposal(BaseModel):
    """A candidate detection rule the model surfaced in its final answer.

    The clause is *not yet validated*; ``core/rules.validate_where_clause``
    runs at pin/draft time (ADR-0005: core owns the gate).
    """

    title: str = Field(description="Short name for this candidate rule.")
    where_clause: str = Field(
        description="A single WHERE-clause filter (no SELECT, no FROM, no table prefixes needed)."
    )
    rationale: str = Field(
        description="Why this pattern looks like fraud worth catching."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions about the data or the pattern's coverage.",
    )


class ModelOutput(BaseModel):
    """What the model should produce as its final answer (typed, not prose)."""

    explanation: str = Field(
        description="Plain-language explanation of what the analysis found."
    )
    assumptions: list[str] = Field(
        default_factory=list, description="Assumptions made about the data or question."
    )
    tables_and_joins_used: list[str] = Field(
        default_factory=list,
        description="The tables and joins the SQL uses (for transparency).",
    )
    rule_proposal: RuleProposal | None = Field(
        default=None,
        description=(
            "If the answer describes a detectable pattern that would make a good "
            "fraud detection rule, fill this with title, where_clause, rationale, "
            "and assumptions. Leave empty if this is just an analysis."
        ),
    )


class Grounding(BaseModel):
    """The full ADR-0006 grounding object. ``sql`` / ``flags`` are facts, not model-reported.

    ``sql`` may be ``None`` — the turn terminated without a fresh query
    (synthesis from prior results, or "the data can't answer").
    """

    sql: str | None
    explanation: str
    assumptions: list[str]
    tables_and_joins_used: list[str]
    flags: list[str]
    rule_proposal: RuleProposal | None = None
