"""In-memory conversational memory tracking state store for the MVP."""

from pydantic_ai.messages import ModelMessage


class SessionManager:
    """Manages chat session history sequences for multi-turn user reasoning."""

    def __init__(self) -> None:
        """Initialize an empty in-memory conversational dictionary registry."""
        self._sessions: dict[str, list[ModelMessage]] = {}

    def get_history(self, session_id: str) -> list[ModelMessage]:
        """Fetch the sequence of historical messages for a given session.

        Args:
            session_id: Target unique session identifier token.

        Returns:
            The list of Pydantic AI model messages recorded so far.
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]

    def save_history(self, session_id: str, history: list[ModelMessage]) -> None:
        """Overwrites or appends the message array sequence back to the session key.

        Args:
            session_id: Target unique session identifier token.
            history: Complete updated message chain list to persist.
        """
        self._sessions[session_id] = history


session_store = SessionManager()
