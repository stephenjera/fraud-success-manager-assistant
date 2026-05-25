from app.domain.investigation.models import StepType
from app.domain.investigation.models import InvestigationSession
from app.core.logger import get_logger

logger = get_logger(__name__)


def decide_next_step(session: InvestigationSession) -> StepType:
    """Controls the deterministic FSM transitions for the Fraud Canvas pipeline."""
    logger.debug(
        "decide_next_step state: sql=%s results=%s insight=%s rule=%s confidence=%s precision=%s",
        bool(session.current_sql),
        bool(session.current_results),
        bool(session.current_insight),
        bool(session.current_rule),
        session.confidence,
        session.current_precision,
    )
    # 1. If no exploratory query has been compiled yet
    if session.current_sql is None:
        return StepType.SQL

    # 2. If SQL query is ready but hasn't run against SQLite yet
    if session.current_results is None:
        return StepType.EXECUTE

    # 3. If query results exist but no narrative summary has been generated
    if session.current_insight is None:
        return StepType.INSIGHT

    # 4. Generate the production WHERE clause rule first so we have concrete mathematical targets
    if session.current_rule is None:
        return StepType.RULE

    # 5. Now check safety metrics or low confidence threshold caps to trigger auto-refinement.
    # If precision is critically low or LLM confidence is flagging, force a refinement lap.
    if session.confidence < 0.5 or session.current_precision < 0.15:
        # Prevent infinite loops: if we just came from a refinement step, break out to FINAL
        if session.steps and session.steps[-1].step_type == StepType.REFINEMENT:
            return StepType.FINAL
        return StepType.REFINEMENT

    # 6. Everything passes metrics thresholds cleanly -> finalize session
    return StepType.FINAL
