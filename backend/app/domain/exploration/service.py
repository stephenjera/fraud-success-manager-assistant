from app.api.schemas import QueryResponse
from app.core.validators import validate_sql
from app.db.connection import Database
from app.db.executor import SQLExecutor
from app.llm.client import LLMService
from app.core.logger import get_logger

logger = get_logger(__name__)


def explore(question: str, schema: str) -> QueryResponse:
    """Lightweight exploration service that maps NL -> SQL -> results.

    This mirrors the existing `query_pipeline` behavior and is intended
    as a migration target for agents to iterate on.
    """
    logger.info("Exploration requested; question length=%d", len(question or ""))

    llm = LLMService()
    db = Database()
    executor = SQLExecutor(db)

    llm_response = llm.safe_generate_sql(question=question, schema=schema)

    validated_sql = validate_sql(llm_response.sql)

    results, _ = executor.execute(validated_sql)

    logger.info("Exploration completed; rows=%d", len(results))

    return QueryResponse(
        sql=validated_sql,
        explanation=llm_response.explanation,
        confidence=llm_response.confidence,
        results=results,
    )
