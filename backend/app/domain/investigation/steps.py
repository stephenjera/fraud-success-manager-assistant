from typing import Any
from app.core.logger import get_logger
from app.core.validators import SQLValidationError, validate_sql
from app.db.connection import Database
from app.db.executor import SQLExecutor
from app.db.schema_loader import load_schema
from app.domain.investigation.models import (
    InvestigationSession,
    InvestigationStep,
    StepType,
)
from app.domain.investigation.metrics import calculate_rule_telemetry
from app.domain.investigation.store import save_session
from app.llm.client import LLMService
from app.domain.investigation.decider import decide_next_step

logger = get_logger(__name__)
llm = LLMService()


def _append_error_step(
    session: InvestigationSession, step_type: StepType, err: Exception
) -> None:
    """Utility helper to record pipeline step trace failures directly into history logs."""
    logger.exception("Error in %s step: %s", step_type, err)
    session.steps.append(
        InvestigationStep(
            step_type=step_type,
            input="error",
            output={"error": str(err)},
        ),
    )


def run_sql_step(session: InvestigationSession) -> InvestigationSession:
    """Asks the LLM service layer to compile initial exploratory SQL code utilizing database schemas."""
    logger.info("run_sql_step start: session=%s question=%s", session.session_id, session.initial_question)
    try:
        schema_text = load_schema()
        response = llm.safe_generate_sql(session.initial_question, schema=schema_text)

        sql = validate_sql(response.sql)
        session.current_sql = sql

        session.steps.append(
            InvestigationStep(
                step_type=StepType.SQL,
                input=session.initial_question,
                output={"sql": sql, "explanation": response.explanation},
            ),
        )
        return save_session(session)

    except Exception as exc:
        _append_error_step(session, StepType.SQL, exc)
        return save_session(session)


def run_execute_step(session: InvestigationSession) -> InvestigationSession:
    """
    Executes the validated exploratory query against the SQLite instance.
    This step strictly handles data extraction, not rule telemetry.
    """
    logger.info("run_execute_step start: session=%s has_sql=%s", session.session_id, bool(session.current_sql))
    if not session.current_sql:
        err = ValueError("No SQL available to execute")
        _append_error_step(session, StepType.EXECUTE, err)
        return save_session(session)

    try:
        validated_sql = validate_sql(session.current_sql)
        logger.debug("Validated SQL (truncated): %s", validated_sql[:500])

        db = Database()
        executor = SQLExecutor(db)
        results, _ = executor.execute(validated_sql)

        row_limit = 1000
        truncated = False
        if len(results) > row_limit:
            results = results[:row_limit]
            truncated = True

        if truncated:
            logger.warning("Results truncated to %d rows for session %s", row_limit, session.session_id)

        session.current_results = results

        output: dict[str, Any] = {"rows": results}
        if truncated:
            output["truncated"] = True

        session.steps.append(
            InvestigationStep(
                step_type=StepType.EXECUTE,
                input=validated_sql,
                output=output,
            ),
        )
        logger.info("run_execute_step complete: session=%s rows=%d truncated=%s", session.session_id, len(results), truncated)
        return save_session(session)

    except Exception as exc:
        _append_error_step(session, StepType.EXECUTE, exc)
        # Attempt recovery via refinement step
        try:
            session = run_refinement_step(session, error=str(exc))
            if session.current_sql:
                validated_sql = validate_sql(session.current_sql)
                db = Database()
                executor = SQLExecutor(db)
                results, _ = executor.execute(validated_sql)

                if len(results) > row_limit:
                    results = results[:row_limit]
                session.current_results = results

                logger.info("Recovered execute after refinement: session=%s rows=%d", session.session_id, len(results))
                session.steps.append(
                    InvestigationStep(
                        step_type=StepType.EXECUTE,
                        input=validated_sql,
                        output={"rows": results, "recovered": True},
                    ),
                )
                return save_session(session)
        except Exception as exc2:
            _append_error_step(session, StepType.EXECUTE, exc2)

        return save_session(session)


def run_insight_step(session: InvestigationSession) -> InvestigationSession:
    """Asks the LLM engine to synthesize a narrative breakdown from the exploration data results."""
    logger.info("run_insight_step start: session=%s results_len=%s", session.session_id, len(session.current_results) if session.current_results is not None else 0)
    if not session.current_sql or session.current_results is None:
        err = ValueError(
            "Missing SQL or results context details for insight generation"
        )
        _append_error_step(session, StepType.INSIGHT, err)
        return save_session(session)

    try:
        insight = llm.generate_insight(
            question=session.initial_question,
            sql=session.current_sql,
            results=session.current_results,
        )

        session.current_insight = insight.summary

        # Dynamically map confidence
        risk = getattr(insight, "risk_level", "medium")
        mapping = {"high": 0.8, "medium": 0.6, "low": 0.4}
        session.confidence = mapping.get(risk.lower(), 0.5)

        logger.info("run_insight_step complete: session=%s confidence=%s", session.session_id, session.confidence)
        session.steps.append(
            InvestigationStep(
                step_type=StepType.INSIGHT,
                input=session.current_sql,
                output=insight.model_dump(),
            ),
        )
        return save_session(session)

    except Exception as exc:
        _append_error_step(session, StepType.INSIGHT, exc)
        return save_session(session)


def _is_safe_where_clause(where: str) -> bool:
    """Ensures raw extracted clause updates cannot route unauthorized DDL/DML mutation strings."""
    forbidden = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
    }
    up = where.upper()
    return not any(kw in up for kw in forbidden)


def run_rule_step(session: InvestigationSession) -> InvestigationSession:
    """
    Generates a production fraud block rule from the insights, and then
    triggers the real-time precision/recall/block-rate mathematical evaluator.
    """
    logger.info("run_rule_step start: session=%s has_sql=%s has_insight=%s results_len=%s", session.session_id, bool(session.current_sql), bool(session.current_insight), len(session.current_results) if session.current_results is not None else 0)
    if not session.current_sql or not session.current_insight:
        err = ValueError(
            "Missing exploratory context or insights required for rule extraction"
        )
        _append_error_step(session, StepType.RULE, err)
        return save_session(session)

    try:
        # LLM builds an explicit FraudRule matching the Pydantic template structure
        rule = llm.generate_rule(
            sql=session.current_sql,
            insight=session.current_insight,
            results=session.current_results or [],
        )

        where_clause = rule.rule_sql_where

        if not where_clause or not where_clause.strip():
            raise ValueError("LLM layer produced empty metadata rule structures")

        if not _is_safe_where_clause(where_clause):
            raise ValueError(
                "Generated structural rule components contain forbidden modification keywords"
            )

        # Strip out loose "WHERE " prefixes if returned by the LLM
        if where_clause.upper().startswith("WHERE "):
            where_clause = where_clause[6:]

        session.current_rule = where_clause
        logger.info("run_rule_step produced rule for session %s: %s", session.session_id, where_clause)

        # --- TELEMETRY ENGINE RUNS HERE ---
        # Evaluate the performance of this newly minted production rule fragment
        telemetry = calculate_rule_telemetry(where_clause)
        logger.debug("Telemetry for session %s: %s", session.session_id, telemetry)

        # Hydrate the session model with real mathematical metrics
        session.current_precision = telemetry["precision"]
        session.current_recall = telemetry["recall"]
        session.current_block_rate = telemetry["block_rate"]
        session.current_status = telemetry["status"]
        session.current_warnings = telemetry["warnings"]

        # Sync global confidence to the structured schema rule limits
        session.confidence = rule.confidence

        session.steps.append(
            InvestigationStep(
                step_type=StepType.RULE,
                input=session.current_insight,
                output={"rule": rule.model_dump(), "telemetry_impact": telemetry},
            ),
        )

        # Log what the decider would choose next (useful for debugging refine loops)
        try:
            next_step = decide_next_step(session)
            logger.info("After RULE step, decide_next_step -> %s for session %s", next_step, session.session_id)
        except Exception:
            logger.exception("Failed to evaluate next step after RULE")

        return save_session(session)

    except Exception as exc:
        _append_error_step(session, StepType.RULE, exc)
        return save_session(session)


def run_refinement_step(
    session: InvestigationSession, error: str | None = None
) -> InvestigationSession:
    """Orchestrates iterative prompt self-healing loops for syntax adjustments."""
    logger.info("run_refinement_step start: session=%s error=%s", session.session_id, bool(error))
    try:
        schema_text = load_schema()
        parts = [
            session.initial_question,
            "REFINE_PREVIOUS_SQL:",
            session.current_sql or "",
            "INSIGHT:",
            session.current_insight or "",
        ]
        if error:
            parts.insert(2, f"DB_ERROR:\n{error}")

        refine_prompt = "\n".join(parts)
        response = llm.safe_generate_sql(refine_prompt, schema=schema_text)

        # Log LLM refine response details for debugging
        try:
            logger.debug("Refinement LLM raw SQL (truncated): %s", (response.sql or '')[:1000])
            logger.info(
                "Refinement LLM returned: confidence=%s explanation=%s",
                getattr(response, "confidence", None),
                (getattr(response, "explanation", None) or "")[:300],
            )
        except Exception:
            logger.exception("Failed to log refinement LLM response details")

        refined_sql = validate_sql(response.sql)
        session.current_sql = refined_sql
        old_conf = session.confidence
        session.confidence = min(1.0, session.confidence + 0.10)
        logger.info(
            "Refinement applied: session=%s old_confidence=%s new_confidence=%s",
            session.session_id,
            old_conf,
            session.confidence,
        )

        logger.info("Refined SQL validated for session %s (truncated): %s", session.session_id, refined_sql[:500])

        session.steps.append(
            InvestigationStep(
                step_type=StepType.REFINEMENT,
                input="auto-refine",
                output={"sql": refined_sql, "confidence": session.confidence},
            ),
        )

        return save_session(session)

    except Exception as exc:
        _append_error_step(session, StepType.REFINEMENT, exc)
        return save_session(session)
