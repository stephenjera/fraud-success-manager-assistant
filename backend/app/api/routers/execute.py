import time
from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends

from app.api.schemas import DataGridResponse, ExecuteRequest
from app.api.services.analytics import execute_raw_sql
from app.api.services.session import ExecutionEvent, execution_store
from app.database import get_analytics_db
from app.logger import get_logger

router = APIRouter()
logger = get_logger("fsm_backend")


@router.post("/execute")
def execute_query(
    payload: ExecuteRequest,
    db: Annotated[duckdb.DuckDBPyConnection, Depends(get_analytics_db)],
) -> DataGridResponse:
    """
    Pure SQL execution layer.

    Responsibilities:
    - Execute read-only SQL
    - Return structured grid results
    - Store execution telemetry (system-only memory)
    """

    sql_text = payload.sql
    safe_sql = " ".join(sql_text.split())

    logger.info("Executing SQL: %s", safe_sql)

    start_time = time.perf_counter()

    try:
        results = execute_raw_sql(db, sql_text)
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

        return DataGridResponse(
            columns=["error"],
            rows=[[str(exc)]],
            execution_time_ms=0.0,
        )

    execution_ms = (time.perf_counter() - start_time) * 1000
    logger.info("Query completed | latency=%.2fms", execution_ms)

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
