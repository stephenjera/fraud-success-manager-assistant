import time
from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, HTTPException

from app.agent.copilot import fsm_copilot_agent
from app.agent.prompts.builder import PROMPT_VERSION
from app.agent.types import AgentDependencies
from app.api.schemas import ExploreRequest, ExploreResponse
from app.api.services.session import ExecutionEvent, execution_store, session_store
from app.database import get_analytics_db
from app.logger import get_logger
from app.observability import (
    flush_langfuse,
    get_langfuse,
    reset_session_context,
    set_session_context,
)

router = APIRouter()
logger = get_logger("fsm_backend")


@router.post("/explore")
async def explore_hypothesis(
    payload: ExploreRequest,
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> ExploreResponse:
    """
    Core single-agent exploration loop.

    Observability (C-1..C-4):
    - Langfuse trace per call with session ID and prompt version
    - Token usage captured via pydantic-ai OTel instrumentation
    - Execution audit trail logged with session, timestamp, SQL, latency
    """
    logger.info("Explore request | session=%s", payload.session_id)

    # C-2: Set session context for token tracking
    set_session_context(payload.session_id)

    # C-1: Create Langfuse trace via start_as_current_observation
    langfuse_client = get_langfuse()
    langfuse_obs = None
    try:
        if langfuse_client:
            langfuse_obs = langfuse_client.start_observation(
                name="fsm_explore",
                as_type="agent",
                input={"prompt": payload.prompt},
                metadata={
                    "session_id": payload.session_id,
                    "prompt_version": PROMPT_VERSION,
                },
            )

        chat_history = session_store.get_history(payload.session_id) or []

        deps = AgentDependencies(
            db=db,
            current_rule_state=payload.current_rule_state,
            execution_context=payload.execution_context,
        )

        start_time = time.perf_counter()

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

        # C-4: Execution audit trail
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

        # C-1: Record trace output in Langfuse
        if langfuse_obs:
            langfuse_obs.update(
                output={
                    "sql": sql,
                    "rule_predicate": predicate,
                    "is_exploratory_only": result.output.is_exploratory_only,
                },
            )
            langfuse_obs.end()
            flush_langfuse()

        logger.info(
            "Explore complete | session=%s | latency=%.2fms",
            payload.session_id,
            duration_ms,
        )

        needs_clarification = getattr(result.output, "needs_clarification", False)
        clarification_request = getattr(result.output, "clarification_request", None)
        confidence = getattr(result.output, "confidence_score", 1.0)

        return ExploreResponse(
            session_id=payload.session_id,
            rationale=result.output.rationale,
            sql=sql,
            rule_predicate=predicate,
            is_exploratory_only=result.output.is_exploratory_only,
            confidence_score=confidence,
            needs_clarification=needs_clarification,
            clarification_request=clarification_request,
        )

    except HTTPException:
        if langfuse_obs:
            langfuse_obs.end()
            flush_langfuse()
        raise

    except Exception as exc:
        logger.exception(
            "Explore failed | session=%s | error=%s",
            payload.session_id,
            str(exc),
        )

        if langfuse_obs:
            langfuse_obs.update(
                output={"error": str(exc)},
                level="ERROR",
            )
            langfuse_obs.end()
            flush_langfuse()

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal agent execution error",
                "error": str(exc),
            },
        )
    finally:
        reset_session_context()
