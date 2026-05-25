from typing import Any

from pydantic import BaseModel

from app.llm.schemas.insight import Insight
from app.llm.schemas.rule import FraudRule


class QueryRequest(BaseModel):
    """Incoming API request."""
    question: str


class QueryResponse(BaseModel):
    sql: str | None
    explanation: str | None
    confidence: float | None
    results: list[dict[str, Any]] | None = None
    error: str | None = None
    insight: Insight | None = None
    rule: FraudRule | None = None


__all__ = ["QueryRequest", "QueryResponse"]
