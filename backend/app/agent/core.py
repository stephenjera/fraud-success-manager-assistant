from collections.abc import Sequence
from dataclasses import dataclass

from pydantic_ai import AgentRunResult, ModelMessage
from pydantic_ai.messages import SystemPromptPart

from app.agent.generator import sql_generator_agent
from app.agent.planner import planner_agent
from app.agent.types import AgentDependencies
from app.logger import get_logger
from app.schemas import SQLResponse

logger = get_logger("fsm_agent_core")


@dataclass
class FSMOrchestrator:

    async def run(
        self,
        user_prompt: str,
        deps: AgentDependencies,
        message_history: Sequence[ModelMessage] | None,
        current_rule_state: str | None = None,
        retries: int = 3,
    ) -> AgentRunResult[SQLResponse]:
        logger.info("Starting planner step")
        logger.debug("User prompt length: %d", len(user_prompt or ""))
        logger.debug("Message history present: %s", bool(message_history))
        logger.debug("Current rule state present: %s", bool(current_rule_state))

        # Inject current_rule_state as a system message if provided
        augmented_history = list(message_history) if message_history else []
        if current_rule_state:
            state_message = ModelMessage.from_parts(
                parts=[
                    SystemPromptPart(
                        content=f"**Active Rule Baseline:**\n{current_rule_state}\n\nPlease refine or iterate on this existing rule based on the incoming user query."
                    )
                ]
            )
            augmented_history.insert(0, state_message)
            logger.info("Injected current_rule_state as system message")
        else:
            augmented_history = message_history

        # Leverage Pydantic AI's native retry mechanism to preserve execution context
        try:
            logger.info("Running planner agent with up to %d native retries", retries)
            plan_result = await planner_agent.run(
                user_prompt=user_prompt,
                message_history=augmented_history,
                retries=retries,
            )
        except Exception as exc:
            logger.exception("Planner failed after native retries")
            raise exc

        plan = plan_result.output
        logger.info("Planner step completed")
        logger.debug(
            "Plan output (truncated): %s", plan.model_dump_json(indent=2)[:1000]
        )

        # Inject current_rule_state into generator input for maximum visibility
        if current_rule_state:
            generator_input = f"""
**CURRENT RULE STATE (to be refined):**
{current_rule_state}

USER QUERY:
{user_prompt}

STRUCTURED PLAN:
{plan.model_dump_json(indent=2)}

Generate SQL query and/or rule predicate.
        """
        else:
            generator_input = f"""
USER QUERY:
{user_prompt}

STRUCTURED PLAN:
{plan.model_dump_json(indent=2)}

Generate SQL query.
        """
        logger.debug("Generator input prepared (truncated): %s", generator_input[:1000])

        logger.info("Starting generator step")

        # By passing the full retry limit natively, ModelRetry exceptions from
        # validate_sql_sandbox are injected back into the LLM conversation context.
        try:
            logger.info("Running generator agent with up to %d native retries", retries)
            sql_result = await sql_generator_agent.run(
                user_prompt=generator_input,
                deps=deps,
                message_history=augmented_history,
                retries=retries,
            )
            logger.info("Generator step completed successfully")
        except Exception as exc:
            logger.exception("Generator failed after native retries")
            raise exc

        try:
            sql_out = sql_result.output
            logger.debug(
                "Generated SQL (truncated): %s",
                getattr(sql_out, "explore_sql", "")[:1000],
            )
        except Exception:
            logger.debug("No SQL output available on result")

        return sql_result


fsm_agent = FSMOrchestrator()
