from app.api.schemas import QueryResponse
from app.core.logger import get_logger
from app.core.validators import validate_sql
from app.db.connection import Database
from app.db.executor import SQLExecutor
from app.llm.client import LLMService

logger = get_logger(__name__)


def run_pipeline(question: str, schema: str) -> QueryResponse:
    """Orchestrate full pipeline: NL -> SQL -> validate -> execute -> insight/rule."""
    logger.info("Running pipeline; question length=%d", len(question or ""))

    llm = LLMService()
    db = Database()
    executor = SQLExecutor(db)

    llm_response = llm.safe_generate_sql(question=question, schema=schema)

    validated_sql = validate_sql(llm_response.sql)

    results, _ = executor.execute(validated_sql)

    logger.info("Pipeline SQL executed; rows=%d", len(results))

    insight = None
    rule = None

    try:
        insight = llm.generate_insight(
            question=question,
            sql=validated_sql,
            results=results,
        )

        rule = llm.generate_rule(
            sql=validated_sql,
            insight=insight.summary,
            results=results,
        )

        logger.info("Insight and rule generated")

    except Exception as e:
        logger.warning("Insight/Rule generation failed: %s", str(e))

    return QueryResponse(
        sql=validated_sql,
        explanation=llm_response.explanation,
        confidence=llm_response.confidence,
        results=results,
        insight=insight,
        rule=rule,
    )
