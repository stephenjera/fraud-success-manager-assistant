"""ADR-0006 typed grounding — the ADR-0006 object the API emits, and the model's output type.

The model writes ``explanation``, ``assumptions``, and ``tables_and_joins_used``.
``structured_output`` (in :mod:`app.agents.graph`) injects the two facts —
``sql`` and ``flags`` — read from the transcript and :mod:`app.core.flags`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    """What the model should produce as its final answer (typed, not prose)."""

    explanation: str = Field(description="Plain-language explanation of what the analysis found.")
    assumptions: list[str] = Field(default_factory=list, description="Assumptions made about the data or question.")
    tables_and_joins_used: list[str] = Field(
        default_factory=list, description="The tables and joins the SQL uses (for transparency)."
    )


class Grounding(BaseModel):
    """The full ADR-0006 grounding object. ``sql`` / ``flags`` are facts, not model-reported."""

    sql: str
    explanation: str
    assumptions: list[str]
    tables_and_joins_used: list[str]
    flags: list[str]
