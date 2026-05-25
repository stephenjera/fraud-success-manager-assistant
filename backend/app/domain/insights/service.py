from typing import Any

from app.llm.client import LLMService
from app.llm.schemas.insight import Insight


def generate_insight(question: str, sql: str, results: list[dict[str, Any]]) -> Insight:
    """Generate an Insight using the existing LLM service."""
    llm = LLMService()
    return llm.generate_insight(question=question, sql=sql, results=results)
