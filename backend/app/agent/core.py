"""
FSM Orchestrator (Single-Agent Architecture).

This module is now a thin execution wrapper around the unified
FSM Co-Pilot agent. It no longer performs:

- Planning
- Prompt stitching
- State mutation

All intelligence is delegated to the agent itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.agent.copilot import fsm_copilot_agent
from app.agent.types import AgentDependencies
from app.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai import AgentRunResult, ModelMessage

    from app.agent.types import AgentDependencies
    from app.schemas import SQLResponse

logger = get_logger("fsm_agent_core")


@dataclass
class FSMOrchestrator:
    """
    Thin orchestration layer for the FSM co-pilot.

    Responsibilities:
    - Pass user input + state to agent
    - Attach dependencies (DB, rule state)
    - Handle retries via pydantic-ai
    """

    async def run(
        self,
        user_prompt: str,
        deps: AgentDependencies,
        message_history: Sequence[ModelMessage] | None,
        current_rule_state: str | None = None,
        retries: int = 3,
    ) -> AgentRunResult[SQLResponse]:
        """
        Execute a single co-pilot turn.

        Args:
            user_prompt: Natural language FSM query
            deps: Runtime dependencies (DB, etc.)
            message_history: Prior conversation state
            current_rule_state: Active CodeMirror rule
            retries: Model retry attempts

        Returns:
            Structured SQLResponse wrapped in AgentRunResult
        """
        logger.info("Starting FSM co-pilot execution")
        logger.debug("User prompt length: %d", len(user_prompt or ""))
        logger.debug("History present: %s", bool(message_history))
        logger.debug("Current rule state present: %s", bool(current_rule_state))

        # Inject rule state into dependencies (NOT message history)
        deps.current_rule_state = current_rule_state

        try:
            result = await fsm_copilot_agent.run(
                user_prompt=user_prompt,
                deps=deps,
                message_history=message_history,
                retries=retries,
            )

            logger.info("FSM co-pilot execution completed successfully")

            try:
                sql_out = result.output
                logger.debug(
                    "Generated SQL (truncated): %s",
                    getattr(sql_out, "explore_sql", "")[:500],
                )
                logger.debug(
                    "Generated predicate: %s",
                    getattr(sql_out, "rule_predicate", None),
                )
            except Exception:
                logger.debug("No structured SQL output available")

            return result

        except Exception as exc:
            logger.exception("FSM co-pilot execution failed after retries")
            raise exc


# Singleton instance used by FastAPI layer
fsm_agent = FSMOrchestrator()
