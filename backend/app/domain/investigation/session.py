from uuid import uuid4

from app.domain.investigation.models import (
    InvestigationSession,
    InvestigationStep,
    StepType,
)


def create_session(question: str) -> InvestigationSession:
    return InvestigationSession(
        session_id=str(uuid4()),
        initial_question=question,
        steps=[],
    )


__all__ = ["InvestigationSession", "InvestigationStep", "StepType", "create_session"]
