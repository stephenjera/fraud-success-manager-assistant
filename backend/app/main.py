"""FastAPI operational routing hub orchestrating incoming FSM UI actions."""

import time
from typing import Annotated

import duckdb
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from app.agent.core import AgentDependencies, fsm_agent
from app.database import get_analytics_db
from app.logger import get_logger
from app.schemas import (
    BacktestRequest,
    BacktestResponse,
    DataGridResponse,
    ExecuteRequest,
    ExploreRequest,
    ExploreResponse,
)
from app.services.analytics import execute_raw_sql, run_backtest
from app.services.session import session_store

logger = get_logger("fsm_backend")


# --- Core Web Application Configuration ---
app = FastAPI(title="Fraud Success Manager Assistant API Server")

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/explore")
async def explore_hypothesis(
    payload: ExploreRequest,
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> ExploreResponse:
    """
    Core FSM loop:
    - Accept natural language hypothesis
    - Run single-agent co-pilot
    - Persist structured memory for iterative reasoning
    """

    logger.info(
        "Explore request | session=%s | prompt=%s",
        payload.session_id,
        payload.user_prompt,
    )

    past_history = session_store.get_history(payload.session_id)
    deps = AgentDependencies(db=db)

    start_time = time.perf_counter()

    try:
        result = await fsm_agent.run(
            user_prompt=payload.user_prompt,
            deps=deps,
            message_history=past_history,
            current_rule_state=payload.current_rule_state,
            retries=5,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        sql = result.output.explore_sql
        predicate = result.output.rule_predicate

        # Initialize new history with past items
        new_history = list(past_history) if past_history else []

        # 1. Append the automatic messages generated during this run (User request + Tool Calls + Structured Responses)
        new_history.extend(result.new_messages())

        # 2. Append the System Observation so the model can contextualize the results in the next turn
        observation = f"""
            SYSTEM OBSERVATION:

            Executed SQL:
            {sql}

            Returned rows: available in data grid

            Rule predicate:
            {predicate}

            NOTE:
            This observation represents real execution feedback.
            Use it for follow-up hypothesis refinement.
            """.strip()

        new_history.append(ModelResponse(parts=[TextPart(content=observation)]))

        session_store.save_history(payload.session_id, new_history)

        logger.info(
            "Explore complete | session=%s | latency=%.2fms",
            payload.session_id,
            duration_ms,
        )

        return ExploreResponse(
            session_id=payload.session_id,
            rationale=result.output.rationale,
            explore_sql=sql,
            rule_predicate=predicate,
            is_exploratory_only=result.output.is_exploratory_only,
        )

    except Exception as e:
        logger.exception("Explore failed")
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@app.post("/api/execute")
def execute_query(
    payload: ExecuteRequest,
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> DataGridResponse:
    """Execute raw or manually tweaked SQL instructions directly inside the sandbox grid."""
    sql_text = payload.sql_query

    logger.info("Executing analytical query payload: %s", sql_text.replace("\n", " "))
    start_time = time.perf_counter()

    try:
        results = execute_raw_sql(db, sql_text)

        if payload.session_id:
            history = session_store.get_history(payload.session_id)
            if history:
                preview_rows = results["rows"][:10]
                observation = (
                    f"SYSTEM OBSERVATION: The previously generated SQL was executed. "
                    f"Columns: {results['columns']} | Returned Rows (Preview): {preview_rows} "
                    f"Ensure you only generate complete, executable SELECT statements or valid isolated WHERE predicates using standard table short-aliases."
                )

                # Ensure structural safety before saving to backend history
                if history and isinstance(history[-1], ModelRequest):
                    history[-1].parts.append(SystemPromptPart(content=observation))
                else:
                    history.append(ModelResponse(parts=[TextPart(content=observation)]))
                session_store.save_history(payload.session_id, history)

    except Exception as exc:
        logger.error(
            "Database compilation or execution failure | Target Query: %s | Error: %s",
            sql_text.replace("\n", " "),
            str(exc),
        )
        # Return a clean 200 containing rows with the error message so the UI can draw it nicely inside the logs grid instead of timing out!
        return DataGridResponse(
            columns=["Compilation Error Details"],
            rows=[[str(exc)]],
            execution_time_ms=0.0,
        )
    else:
        execution_ms = (time.perf_counter() - start_time) * 1000
        logger.info("Query completed cleanly | Latency: %.2fms", execution_ms)

        results["execution_time_ms"] = round(execution_ms, 2)
        return DataGridResponse(**results)


@app.post("/api/backtest")
def evaluate_rule(
    payload: BacktestRequest, 
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> BacktestResponse:
    """Backtest a custom WHERE rule fragment over full historical metrics."""
    clause_text = payload.where_clause

    logger.info(
        "Initiating historical rule backtest evaluation | Fragment: %s", clause_text
    )
    start_time = time.perf_counter()

    try:
        metrics = run_backtest(db, clause_text)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Backtest calculation completed | Latency: %.2fms | Blocked Records: %s | Saved Value: $%0.2f",
            duration_ms,
            metrics["metrics"]["true_positives"]
            + metrics["metrics"]["false_positives"],
            metrics["metrics"]["total_fraud_value_saved_usd"],
        )
        return BacktestResponse(**metrics)
    except Exception as exc:
        logger.error(
            "Backtester verification crash | Evaluated Fragment: %s | Error: %s",
            clause_text,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backtester Compile Error: {str(exc)}",
        ) from exc
