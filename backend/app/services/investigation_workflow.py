from app.domain.investigation.fsm import InvestigationFSM
from app.domain.investigation.models import (
    InvestigationStep,
    StepType,
    WorkspaceSnapshot,
)
from app.domain.investigation.models import InvestigationSession
from app.domain.investigation.store import (
    create_session,
    get_session,
    save_session,
)

from app.core.logger import get_logger

logger = get_logger(__name__)
CUTOFF_LENGTH = 35


def run_investigation(
    session_id: str,
    question: str,
    mode: str = "new",
) -> InvestigationSession:
    """Run the investigation FSM with Snapshot-based state tracking logic."""
    logger.info("run_investigation start: session_id=%s mode=%s question=%s", session_id, mode, question)
    session = get_session(session_id)

    if session is None:
        session = create_session(session_id, question)
        logger.info("Created new session: %s", session.session_id)
        session.session_name = (
            f"{question[:CUTOFF_LENGTH]}..."
            if len(question) > CUTOFF_LENGTH
            else question
        )
        save_session(session)

    elif mode == "refine":
        # 1. Take a clean snapshot of the working memory state before resetting fields
        if session.current_sql and session.current_insight:
            next_version = len(session.history) + 1

            # Determine what prompt generated the *current* state we are archiving
            current_prompt = session.initial_question
            if session.steps:
                ref_steps = [
                    s for s in session.steps if s.step_type == StepType.REFINEMENT
                ]
                if ref_steps and isinstance(ref_steps[-1].output, dict):
                    current_prompt = ref_steps[-1].output.get(
                        "new_question", current_prompt
                    )

            # Hydrating telemetry lineage additions directly into the snapshot log
            snapshot = WorkspaceSnapshot(
                version=next_version,
                prompt=current_prompt,
                sql=session.current_sql,
                record_count=len(session.current_results)
                if session.current_results
                else 0,
                insight=session.current_insight,
                rule=session.current_rule,
                precision=session.current_precision,
                recall=session.current_recall,
                block_rate=session.current_block_rate,
                status=session.current_status,
                warnings=session.current_warnings,
            )
            session.history.append(snapshot)

        # 2. Reset the active tracking fields so the state engine runs fresh rules
        session.current_sql = None
        session.current_results = None
        session.current_insight = None
        session.current_rule = None
        session.current_precision = 0.0
        session.current_recall = 0.0
        session.current_block_rate = 0.0
        session.current_status = "ACCEPTED"
        session.current_warnings = []
        session.done = False

        # Update the tracking prompt context so the FSM knows about the refinement text
        session.initial_question = question

        session.steps.append(
            InvestigationStep(
                step_type=StepType.REFINEMENT,
                input="refine",
                output={"new_question": question},
            )
        )
        save_session(session)

    elif question and question != session.initial_question:
        session.steps.append(
            InvestigationStep(
                step_type=StepType.REFINEMENT,
                input="followup_question",
                output={
                    "previous_question": session.initial_question,
                    "new_question": question,
                },
            ),
        )
        session.initial_question = question
        session.session_name = (
            f"{question[:CUTOFF_LENGTH]}..."
            if len(question) > CUTOFF_LENGTH
            else question
        )
        session.history = []  # Clear ancestral paths logs
        session.current_sql = None
        session.current_results = None
        session.current_insight = None
        session.current_rule = None

        # Clear persistent metric slots
        session.current_precision = 0.0
        session.current_recall = 0.0
        session.current_block_rate = 0.0
        session.current_status = "ACCEPTED"
        session.current_warnings = []

        session.confidence = 0.0
        session.done = False
        save_session(session)

    fsm = InvestigationFSM()

    # Fixed execution loop cycle safety bounds
    logger.info("Starting FSM loop for session %s", session.session_id)
    for i in range(5):
        if session.done:
            logger.info("Session marked done, breaking FSM loop: %s", session.session_id)
            break
        logger.debug("FSM iteration %d for session %s", i + 1, session.session_id)
        session = fsm.run(session)

    logger.info(
        "FSM loop complete: session=%s done=%s steps=%d",
        session.session_id,
        session.done,
        len(session.steps),
    )

    save_session(session)

    # Explicit terminal log to indicate process completion and waiting state
    if session.done:
        logger.info(
            "Investigation finished: session=%s status=%s confidence=%s — waiting for user to close or start a new investigation",
            session.session_id,
            session.current_status,
            session.confidence,
        )
    else:
        logger.info(
            "Investigation paused: session=%s done=%s status=%s confidence=%s — awaiting user refinement or follow-up question",
            session.session_id,
            session.done,
            session.current_status,
            session.confidence,
        )

    return session
