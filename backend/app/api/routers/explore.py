import time
from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, HTTPException

from app.agent.copilot import fsm_copilot_agent
from app.agent.types import AgentDependencies
from app.api.schemas import ExploreRequest, ExploreResponse
from app.api.services.session import ExecutionEvent, execution_store, session_store
from app.database import get_analytics_db
from app.logger import get_logger

router = APIRouter()
logger = get_logger("fsm_backend")


@router.post("/explore")
async def explore_hypothesis(
    payload: ExploreRequest,
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> ExploreResponse:
    """
    Core single-agent exploration loop.

    Responsibilities:
    - Run LLM co-pilot
    - Persist conversational memory only
    - Persist execution telemetry separately
    - Inject structured execution context for grounded reasoning
    """
    logger.info("Explore request | session=%s", payload.session_id)

    chat_history = session_store.get_history(payload.session_id) or []

    deps = AgentDependencies(
        db=db,
        current_rule_state=payload.current_rule_state,
        execution_context=payload.execution_context,  # 🔥 grounding signal
    )

    start_time = time.perf_counter()

    try:

        result = await fsm_copilot_agent.run(
            user_prompt=payload.prompt,
            deps=deps,
            message_history=chat_history,
            retries=5,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        sql = result.output.explore_sql
        predicate = result.output.rule_predicate

        updated_chat_history = list(chat_history)
        updated_chat_history.extend(result.new_messages())

        session_store.save_history(
            payload.session_id,
            updated_chat_history,
        )

        execution_store.append(
            session_id=payload.session_id,
            event=ExecutionEvent(
                sql=sql,
                columns=None,
                row_count=None,
                preview_rows=None,
                execution_ms=duration_ms,
            ),
        )

        logger.info(
            "Explore complete | session=%s | latency=%.2fms",
            payload.session_id,
            duration_ms,
        )

        return ExploreResponse(
            session_id=payload.session_id,
            rationale=result.output.rationale,
            sql=sql,
            rule_predicate=predicate,
            is_exploratory_only=result.output.is_exploratory_only,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Explore failed | session=%s | error=%s",
            payload.session_id,
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal agent execution error",
                "error": str(exc),
            },
        )
