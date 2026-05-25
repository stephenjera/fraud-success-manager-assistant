from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field


class StepType(str, Enum):
    SQL = "sql"
    EXECUTE = "execute"
    INSIGHT = "insight"
    RULE = "rule"
    REFINEMENT = "refinement"
    FINAL = "final"


class InvestigationStep(BaseModel):
    step_type: StepType
    input: str | dict[str, Any]
    output: Any


class WorkspaceSnapshot(BaseModel):
    version: int
    prompt: str
    sql: str
    record_count: int
    insight: str
    rule: str | None = None
    # Telemetry Lineage Additions
    precision: float = 0.0
    recall: float = 0.0
    block_rate: float = 0.0
    status: str = "ACCEPTED"
    warnings: list[str] = Field(default_factory=list)


class InvestigationSession(BaseModel):
    session_id: str
    initial_question: str
    session_name: str = "New Fraud Investigation"

    steps: Annotated[list[InvestigationStep], Field(default_factory=list)]
    history: Annotated[list[WorkspaceSnapshot], Field(default_factory=list)]

    # Active working parameters
    current_sql: str | None = None
    current_results: list[dict[str, Any]] | None = None
    current_insight: str | None = None
    current_rule: str | None = None

    # Persistent Real-time Telemetry Engine Slots
    current_precision: float = 0.0
    current_recall: float = 0.0
    current_block_rate: float = 0.0
    current_status: str = "ACCEPTED"
    current_warnings: list[str] = Field(default_factory=list)

    confidence: float = 0.0
    done: bool = False
