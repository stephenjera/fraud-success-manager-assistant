from fastapi import APIRouter, HTTPException, status

from app.domain.investigation.models import InvestigationSession
from app.domain.investigation.store import get_session, save_session
from app.services.investigation_workflow import run_investigation

router = APIRouter()
from app.core.logger import get_logger

logger = get_logger(__name__)


@router.post("/investigation/run")
def investigation_run(session_id: str, question: str, mode: str = "new"):
    logger.info("API investigation_run called: session_id=%s mode=%s question=%s", session_id, mode, question)
    return run_investigation(session_id, question, mode)


@router.get("/investigation/{session_id}")
def investigation_get(session_id: str):
    session = get_session(session_id)

    # If it doesn't exist, don't 404. Return a clean initial schema state.
    if session is None:
        return InvestigationSession(
            session_id=session_id,
            initial_question="",
            session_name="Active Fraud Investigation Canvas",
            steps=[],
            history=[],
        )

    return session


@router.post("/investigation/{session_id}/rollback/{version_id}")
def investigation_rollback(session_id: str, version_id: int):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session context not found")

    target_snapshot = next(
        (s for s in session.history if s.version == version_id),
        None,
    )
    if not target_snapshot:
        raise HTTPException(
            status_code=422,
            detail="Specified snapshot target version index missing",
        )

    # Rehydrate the exact metrics profile along with matching working queries
    session.current_sql = target_snapshot.sql
    session.current_insight = target_snapshot.insight
    session.current_rule = target_snapshot.rule
    session.current_precision = target_snapshot.precision
    session.current_recall = target_snapshot.recall
    session.current_block_rate = target_snapshot.block_rate
    session.current_status = target_snapshot.status
    session.current_warnings = target_snapshot.warnings
    session.current_results = []

    # Slice timeline trace arrays cleanly
    session.history = [s for s in session.history if s.version < version_id]
    session.done = False

    save_session(session)
    return session


@router.post("/investigation/{session_id}/rename")
def investigation_rename(session_id: str, new_name: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session context not found"
        )
    session.session_name = new_name
    save_session(session)
    return session
