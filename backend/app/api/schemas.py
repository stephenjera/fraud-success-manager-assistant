"""
Data schemas for FastAPI + Agent + Rule Evaluation system.

Design goals:
- Clear domain separation (exploration vs rules vs execution)
- Remove ambiguous naming like "backtest"
- Improve OpenAPI readability
- Make testing easier via explicit request/response contracts
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# =========================================================
# AGENT OUTPUT (Exploration Layer)
# =========================================================


class SQLResponse(BaseModel):
    """
    Core structured output from the LLM co-pilot.

    This is the single source of truth for:
    - exploratory SQL
    - rule extraction
    """

    rationale: str = Field(
        description="High-level explanation of the reasoning behind the generated SQL and rule logic.",
        examples=["Fraud spikes correlate with high-value MCC categories..."],
    )

    explore_sql: str = Field(
        description="Full executable SELECT query used to populate the analytics grid.",
        examples=["SELECT * FROM transactions t LIMIT 100;"],
    )

    rule_predicate: str | None = Field(
        default=None,
        description="Isolated WHERE clause used for rule evaluation. Null if purely exploratory.",
        examples=["t.amount_usd_cents > 50000 AND mc.mcc = '5967'"],
    )

    is_exploratory_only: bool = Field(
        description="Indicates whether the query is purely analytical with no rule extraction intent.",
        examples=[True, False],
    )


class ExploreRequest(BaseModel):
    """User prompt sent to the LLM exploration system."""

    session_id: str = Field(
        description="Conversation/session identifier used for memory continuity.",
        examples=["sess_12345"],
    )

    prompt: str = Field(
        description="Natural language hypothesis or instruction for fraud exploration.",
        examples=["Why are fraud rates increasing in high-value transactions?"],
    )

    current_rule_state: str | None = Field(
        default=None,
        description="Current WHERE clause being edited in UI (optional context injection).",
        examples=["t.amount_usd_cents > 10000"],
    )
    
    execution_context: dict | None = Field(
        default=None,
        description="Structured execution results used for rule synthesis grounding.",
    )


class ExploreResponse(BaseModel):
    """Structured response returned from the LLM exploration endpoint."""

    session_id: str

    rationale: str
    sql: str

    rule_predicate: str | None = None

    is_exploratory_only: bool


# =========================================================
#  RULE EVALUATION
# =========================================================


class RuleEvaluationRequest(BaseModel):
    """
    Request to evaluate a WHERE clause against historical dataset.

    This replaces the old 'BacktestRequest'.
    """

    where_clause: str = Field(
        ...,
        description="SQL WHERE clause used to evaluate fraud detection performance.",
        examples=["t.amount_usd_cents > 50000 AND mc.mcc = '5967'"],
    )


class RuleMetrics(BaseModel):
    """Core evaluation metrics for a fraud rule."""

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int

    precision: float
    recall: float
    false_positive_rate: float

    fraud_value_caught: float
    legit_value_blocked: float
    net_value: float


class RuleEvaluationResponse(BaseModel):
    """
    Response from rule evaluation engine.

    Used to power:
    - rule ranking
    - dashboards
    - optimization loops
    """

    metrics: RuleMetrics


# =========================================================
# RAW EXECUTION LAYER (Data Grid)
# =========================================================


class ExecuteRequest(BaseModel):
    """Raw SQL execution request for analytics grid."""

    session_id: str | None = Field(
        default=None,
        description="Optional session tracking ID for associating execution results.",
    )

    sql: str = Field(
        ...,
        description="Read-only SELECT query executed against DuckDB.",
        examples=["SELECT * FROM transactions LIMIT 10;"],
    )


class DataGridResponse(BaseModel):
    """Tabular response for frontend data grid rendering."""

    columns: list[str]
    rows: list[list[Any]]

    execution_time_ms: float


# =========================================================
# RULE MANAGEMENT (future-ready foundation)
# =========================================================


class RuleSaveRequest(BaseModel):
    """Persist a validated fraud rule."""

    rule_name: str
    where_clause: str

    metrics: RuleMetrics


class RuleSaveResponse(BaseModel):
    rule_id: str


# =========================================================
# SESSION MEMORY
# =========================================================


class SessionHistoryResponse(BaseModel):
    session_id: str
    history: list[dict]


# =========================================================
# OPTIONAL ANALYTICS EXTENSION (kept minimal)
# =========================================================


class TimelineDataPoint(BaseModel):
    """Single point in a time-series evaluation (future use)."""

    date: str = Field(description="ISO date string for aggregation bucket.")

    fraud_blocked: int
    legitimate_blocked: int


# (Intentionally NOT expanding backtest timeline yet — keep lean)
