from pydantic_ai.messages import ModelResponse, TextPart

from app.api.services.session import session_store


def append_execution_observation(session_id: str, observation: str):
    history = session_store.get_history(session_id)

    if not history:
        return

    history.append(ModelResponse(parts=[TextPart(content=observation)]))

    session_store.save_history(session_id, history)
