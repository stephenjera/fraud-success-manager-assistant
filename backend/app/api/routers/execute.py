import time
from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends

from app.api.schemas import DataGridResponse, ExecuteRequest
from app.api.services.analytics import execute_raw_sql
from app.api.services.query_safety import enforce_row_limit, validate_statement_type
from app.api.services.session import ExecutionEvent, execution_store
from app.config import settings
from app.database import get_analytics_db
from app.logger import get_logger
from app.observability import (
    flush_langfuse,
    get_langfuse,
)

router = APIRouter()
logger = get_logger("fsm_backend")


@router.post("/execute")
async def execute_query(
    payload: ExecuteRequest,
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> DataGridResponse:
    """
    Pure SQL execution layer.

    Safety guardrails:
    - A-3: Statement-type validation (reject non-SELECT)
    - A-4: Row-limit cap (enforced via LIMIT injection)
    - A-5: Query timeout (anyio async timeout)

    Observability (C-4):
    - Langfuse trace for each SQL execution with audit metadata
    """

    sql_text = payload.sql
    safe_sql = " ".join(sql_text.split())

    # C-4: Langfuse trace for execution audit trail
    langfuse_client = get_langfuse()
    langfuse_obs = None
    if payload.session_id and langfuse_client:
        langfuse_obs = langfuse_client.start_observation(
            name="fsm_execute",
            as_type="tool",
            input={"sql": safe_sql},
            metadata={"session_id": payload.session_id},
        )

    # A-3: Reject unsafe statements
    error = validate_statement_type(sql_text)
    if error:
        logger.warning("Rejected unsafe query: %s", error)
        if langfuse_obs:
            langfuse_obs.update(
                output={"error": error},
                level="WARNING",
            )
            langfuse_obs.end()
            flush_langfuse()
        return DataGridResponse(
            columns=["error"],
            rows=[[error]],
            execution_time_ms=0.0,
        )

    # A-4: Enforce row limit
    sql_text = enforce_row_limit(sql_text)

    logger.info("Executing SQL: %s", safe_sql)

    start_time = time.perf_counter()

    results: dict | None = None

    async def _run_query() -> None:
        nonlocal results
        results = execute_raw_sql(db, sql_text)

    import anyio
    with anyio.move_on_after(settings.QUERY_TIMEOUT_SECONDS):
        await _run_query()

    if results is None:
        exc_msg = f"Query timed out after {settings.QUERY_TIMEOUT_SECONDS}s"
        execution_ms = (time.perf_counter() - start_time) * 1000
        logger.error(exc_msg)
        if langfuse_obs:
            langfuse_obs.update(
                output={"error": exc_msg, "execution_ms": execution_ms},
                level="ERROR",
            )
            langfuse_obs.end()
            flush_langfuse()
        return DataGridResponse(
            columns=["error"],
            rows=[[exc_msg]],
            execution_time_ms=execution_ms,
        )

    try:
        logger.info(
            "EXECUTION_RESULT_SUMMARY | columns=%s | sample_rows=%s",
            results.get("columns"),
            results.get("rows")[:3],
        )

    except Exception as exc:
        logger.error(
            "SQL execution failed | query=%s | error=%s",
            safe_sql,
            str(exc),
        )

        execution_ms = (time.perf_counter() - start_time) * 1000
        if langfuse_obs:
            langfuse_obs.update(
                output={"error": str(exc), "execution_ms": execution_ms},
                level="ERROR",
            )
            langfuse_obs.end()
            flush_langfuse()

        return DataGridResponse(
            columns=["error"],
            rows=[[str(exc)]],
            execution_time_ms=execution_ms,
        )

    execution_ms = (time.perf_counter() - start_time) * 1000
    logger.info("Query completed | latency=%.2fms", execution_ms)

    if langfuse_obs:
        langfuse_obs.update(
            output={
                "row_count": len(results.get("rows", [])),
                "execution_ms": execution_ms,
            },
        )
        langfuse_obs.end()
        flush_langfuse()

    columns = results.get("columns") if isinstance(results, dict) else None
    rows = results.get("rows") if isinstance(results, dict) else []

    if rows is None:
        rows = []

    if columns is None:
        columns = []

    # Attach timing
    response_payload = {
        "columns": columns,
        "rows": rows,
        "execution_time_ms": round(execution_ms, 2),
    }

    if payload.session_id:
        try:
            execution_store.append(
                session_id=payload.session_id,
                event=ExecutionEvent(
                    sql=sql_text,
                    columns=columns,
                    row_count=len(rows),
                    preview_rows=rows[:5],
                    execution_ms=execution_ms,
                ),
            )

        except Exception as hook_exc:
            logger.warning(
                "Execution telemetry failed | session_id=%s | error=%s",
                payload.session_id,
                str(hook_exc),
            )

    return DataGridResponse(**response_payload)
