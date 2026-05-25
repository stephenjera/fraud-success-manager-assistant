from pydantic import BaseModel, Field


class SQLResponse(BaseModel):
    """Structured response from the LLM."""
    sql: str = Field(description="Valid SQLite SELECT query")
    explanation: str = Field(description="Short explanation of the query")
    confidence: float = Field(ge=0, le=1)


__all__ = ["SQLResponse"]
