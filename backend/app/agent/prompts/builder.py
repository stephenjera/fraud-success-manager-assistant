"""
Unified prompt builder for the FSM single-agent co-pilot architecture.

This module constructs a full-fidelity prompt by injecting:
- System instructions
- Database schema
- Conversation history
- System observations (execution feedback)
- Current rule state (CodeMirror)
- Latest user request

No planning layer. No abstraction. No transformation.
Everything is passed through as raw context.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic_ai.messages import ModelMessage

PROMPT_VERSION = "v3.0"


def _load(name: str) -> str:
    """Load a prompt file from disk."""
    return (Path(__file__).parent / f"{name}.txt").read_text().strip()


def _format_conversation(history: Sequence[ModelMessage] | None) -> str:
    """
    Convert structured message history into a readable flat string.

    We intentionally keep this lossy-but-readable instead of raw JSON
    because LLMs reason better over clean conversational transcripts.
    """
    if not history:
        return "None"

    formatted = []
    for msg in history:
        role = msg.__class__.__name__.replace("Model", "").replace("Message", "")
        try:
            content = " ".join([p.content for p in msg.parts if hasattr(p, "content")])
        except Exception:
            content = str(msg)

        formatted.append(f"{role.upper()}: {content}")

    return "\n".join(formatted)


def _extract_system_observations(history: Sequence[ModelMessage] | None) -> str:
    """
    Extract SYSTEM OBSERVATION messages injected after SQL execution.

    These are critical for:
    - "for this" references
    - iterative hypothesis refinement
    - preventing redundant queries
    """
    if not history:
        return "None"

    observations = []

    for msg in history:
        for part in getattr(msg, "parts", []):
            content = getattr(part, "content", "")
            if isinstance(content, str) and "SYSTEM OBSERVATION" in content:
                observations.append(content)

    return "\n\n".join(observations) if observations else "None"


def build_copilot_prompt(
    *,
    schema: str,
    message_history: Sequence[ModelMessage] | None,
    current_rule_state: str | None,
    user_prompt: str,
) -> str:
    """
    Construct the full single-agent prompt.

    This is the ONLY prompt entry point in the new architecture.
    """
    system_prompt = _load("system")

    conversation_text = _format_conversation(message_history)
    system_observations = _extract_system_observations(message_history)

    return f"""
        {system_prompt}

        --- DATABASE SCHEMA ---
        ```sql
        {schema}

        --- CONVERSATION HISTORY ---
        {conversation_text}

        --- SYSTEM OBSERVATIONS ---
        {system_observations}

        --- CURRENT RULE STATE (CODEMIRROR) ---
        {current_rule_state or "None"}

        --- USER REQUEST ---
        {user_prompt}

        PROMPT_VERSION: {PROMPT_VERSION}
        """.strip()
