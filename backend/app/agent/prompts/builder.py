"""
Unified prompt builder for the FSM single-agent co-pilot architecture.

Now upgraded with:
- Execution context grounding (critical fix)
- Hybrid human + structured formatting
- Strong rule synthesis constraints
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic_ai.messages import ModelMessage

PROMPT_VERSION = "v4.0"


def _load(name: str) -> str:
    """Load a prompt file from disk."""
    return (Path(__file__).parent / f"{name}.txt").read_text().strip()


def _format_conversation(history: Sequence[ModelMessage] | None) -> str:
    """
    Convert structured message history into readable transcript.
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
    Extract SYSTEM OBSERVATION messages from history.
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


# =========================================================
# NEW: execution context formatter (HYBRID MODE)
# =========================================================


def _format_execution_context(context: dict | None) -> str:
    """
    Convert execution results into LLM-friendly grounded signals.

    HYBRID FORMAT:
    - Human-readable ranking
    - Structured raw JSON for fidelity
    """
    if not context:
        return "None"

    signals = context.get("signals", [])
    top = context.get("top_signal")

    if not signals:
        return "No signals available"

    lines = []

    lines.append("TOP FRAUD SIGNAL:")
    if top:
        lines.append(
            f"- {top.get('feature_value')} "
            f"({top.get('fraud_count')} fraud cases, "
            f"{top.get('fraud_rate')} rate)"
        )

    lines.append("\nRANKED SIGNALS:")

    for s in signals[:10]:  # prevent prompt explosion
        lines.append(
            f"- {s.get('feature_value')} | "
            f"fraud_count={s.get('fraud_count')} | "
            f"fraud_rate={s.get('fraud_rate')}"
        )

    lines.append("\nRAW CONTEXT (for fidelity):")
    lines.append(str(context))

    return "\n".join(lines)


# =========================================================
# MAIN PROMPT BUILDER
# =========================================================


def build_copilot_prompt(
    *,
    schema: str,
    message_history: Sequence[ModelMessage] | None,
    current_rule_state: str | None,
    user_prompt: str,
    execution_context: dict | None = None,
) -> str:
    """
    Construct full LLM prompt for FSM co-pilot.

    This is the ONLY entry point for reasoning.
    """

    system_prompt = _load("system")

    conversation_text = _format_conversation(message_history)
    system_observations = _extract_system_observations(message_history)
    execution_block = _format_execution_context(execution_context)

    return f"""
    {system_prompt}

    # =========================================================
    # DATABASE SCHEMA
    # =========================================================
    ```sql
    {schema}
    =========================================================
    CONVERSATION HISTORY
    =========================================================

    {conversation_text}

    =========================================================
    SYSTEM OBSERVATIONS
    =========================================================

    {system_observations}

    =========================================================
    EXECUTION CONTEXT (MOST IMPORTANT SIGNAL)
    Use this as PRIMARY SOURCE OF TRUTH for rule generation.
    =========================================================

    {execution_block}

    =========================================================
    CURRENT RULE STATE (CODEMIRROR)
    =========================================================

    {current_rule_state or "None"}

    =========================================================
    USER REQUEST
    =========================================================

    {user_prompt}

    =========================================================
    RULE SYNTHESIS INSTRUCTIONS (CRITICAL)
    =========================================================
    ONLY use values present in EXECUTION CONTEXT for rule creation
    NEVER invent fraud categories or error types
    Prefer TOP FRAUD SIGNAL when forming rules
    Combine signals ONLY if explicitly similar in meaning
    If execution context is empty, default to exploratory behavior

    EXECUTION CONTEXT CONTRACT:

    You are given ranked fraud signals.

    RULE:
    - Use ONLY signals[0].feature_value unless explicitly told otherwise
    - NEVER output placeholders like <TOP_FRAUD_ERROR_TYPE>
    - NEVER output NULL-based logic
    - Your rule MUST reference real observed values

    PROMPT_VERSION: {PROMPT_VERSION}
    """.strip()
