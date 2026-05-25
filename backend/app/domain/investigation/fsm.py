from app.domain.investigation.decider import decide_next_step
from app.domain.investigation.models import StepType
from app.domain.investigation.models import InvestigationSession
from app.domain.investigation.steps import (
    run_execute_step,
    run_insight_step,
    run_refinement_step,
    run_rule_step,
    run_sql_step,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


class InvestigationFSM:
    def run(self, session: InvestigationSession) -> InvestigationSession:
        """Evaluates active session parameters and dispatches the corresponding engineering pipeline step."""
        step = decide_next_step(session)
        logger.info("FSM dispatch: session=%s next_step=%s", getattr(session, "session_id", None), step)

        if step == StepType.SQL:
            return run_sql_step(session)

        if step == StepType.EXECUTE:
            return run_execute_step(session)

        if step == StepType.INSIGHT:
            return run_insight_step(session)

        if step == StepType.RULE:
            return run_rule_step(session)

        if step == StepType.REFINEMENT:
            return run_refinement_step(session)

        if step == StepType.FINAL:
            session.done = True
            return session

        return session
