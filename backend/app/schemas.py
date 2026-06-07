"""Data schemas for API transportation layer and structured agent execution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- Unified Agent Structural Target ---
class SQLResponse(BaseModel):
    """The master dual-output structure forced out of the text-to-SQL engine."""

    rationale: str = Field(
        description="Internal chain-of-thought explanation of the data discovery and isolation strategy."
    )
    explore_sql: str = Field(
        description="A complete, executable SELECT query using system short-aliases to populate the UI data grid dashboard."
    )
    rule_predicate: str | None = Field(
        default=None,
        description="An isolated WHERE clause fragment using standard table short-aliases meant for real-time sandbox backtesting. Left blank if is_exploratory_only is True.",
    )
    is_exploratory_only: bool = Field(
        description="Flag specifying if the request was purely analytical/informational, requiring no fraud rule isolation logic."
    )


class QueryPlan(BaseModel):
    """Structured processing model utilized during the initial planning layer."""

    intent: str = Field(..., min_length=1)
    group_by: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)

    class Config:
        """Pydantic model structural configuration layout."""

        extra = "ignore"


# --- HTTP API Web Contracts ---
class ExploreRequest(BaseModel):
    """State-aware natural language incoming request parameter payload from the UI."""

    session_id: str = Field(
        description="Unique tracking token for conversation history state consistency."
    )
    user_prompt: str = Field(
        description="The conversational text input describing a fraud hypothesis or refinement command."
    )
    current_rule_state: str | None = Field(
        default=None,
        description="The literal active WHERE predicate code currently sitting inside the user's UI CodeMirror editor workspace.",
    )


class ExploreResponse(BaseModel):
    """Outgoing structured data package destined to update the entire frontend workspace."""

    session_id: str
    rationale: str
    explore_sql: str
    rule_predicate: str | None = None
    is_exploratory_only: bool


class ExecuteRequest(BaseModel):
    """Payload tracking raw or manually optimized full SELECT queries to run in the grid window."""

    session_id: str | None = Field(
        default=None,
        description="Optional tracking token to inject execution results back into agent memory.",
    )
    sql_query: str = Field(
        ...,
        description="The clean, read-only SELECT query string to execute against DuckDB.",
        examples=["SELECT * FROM transactions LIMIT 10;"],
    )


class BacktestRequest(BaseModel):
    """Payload tracking a specific SQL predicate clause to evaluate rule telemetry performance."""

    where_clause: str = Field(
        ...,
        description="The isolated WHERE constraint string used to run simulations on historical datasets.",
        examples=["t.amount_usd_cents > 50000 AND mc.mcc = '5967'"],
    )


# --- Outbound Response Telemetry ---
class DataGridResponse(BaseModel):
    """The formatted data matrix returned to populate the UI data viewer."""

    columns: list[str] = Field(description="Array of ordered column header labels.")
    rows: list[list[Any]] = Field(
        description="Two-dimensional matrix containing matching data row records."
    )
    execution_time_ms: float = Field(
        description="Telemetry pinpointing real database performance duration."
    )


class BacktestMetrics(BaseModel):
    """The calculated high-level KPI blocks for rule evaluation."""

    true_positives: int = Field(
        description="Fraud events caught accurately matching the constraint."
    )
    false_positives: int = Field(
        description="Legitimate customer volume trapped mistakenly by the proposed clause."
    )
    false_positive_ratio: float = Field(
        description="The statistical precision noise indicator (FP / Total Blocked)."
    )
    total_fraud_value_saved_usd: float = Field(
        description="Financial aggregate calculation of saved dollar totals."
    )


class TimelineDataPoint(BaseModel):
    """A single unified point along a chronological line chart."""

    date: str = Field(
        description="ISO text representation of the target observation day."
    )
    fraud_blocked: int = Field(
        description="Count of actual true malicious occurrences intercepted."
    )
    legitimate_blocked: int = Field(
        description="Count of clear consumer profiles mistakenly interrupted."
    )


class BacktestResponse(BaseModel):
    """The top-level operational simulation payload returned to construct analytics dashboards."""

    metrics: BacktestMetrics
    timeline_series: list[TimelineDataPoint]
