from typing import Any

from app.domain.investigation.models import (
    InvestigationSession,
    InvestigationStep,
    StepType,
)


def add_step(
    session: InvestigationSession,
    step_type: StepType,
    input_data: str,
    output: dict[str, Any] | str | None,
):
    session.steps.append(
        InvestigationStep(
            step_type=step_type,
            input=input_data,
            output=output,
        )
    )
    return session
