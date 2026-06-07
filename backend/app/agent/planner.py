"""Planner agent: converts user intent → structured execution plan."""

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.prompts.builder import build_planner_prompt
from app.config import settings
from app.database import SCHEMA_DDL
from app.logger import get_logger
from app.schemas import QueryPlan, SQLResponse

sql_generator_agent = Agent(
    model=settings.LLM_MODEL,
    output_type=SQLResponse,
)

planner_agent = Agent(
    model=settings.LLM_MODEL,
    output_type=QueryPlan,
)

logger = get_logger("planner_agent")


@planner_agent.system_prompt
def planner_prompt(_: RunContext) -> str:
    logger.info("Building planner system prompt")
    logger.debug("Schema DDL length: %d characters", len(SCHEMA_DDL or ""))
    prompt = build_planner_prompt(SCHEMA_DDL)
    logger.debug("Planner prompt built (truncated): %s", prompt[:200])
    return prompt


@planner_agent.output_validator
def planner_raw_text_logger(ctx: RunContext, text_or_obj) -> object:
    """Log raw text emitted by the model before parsing into `QueryPlan`.

    This validator is resilient: pydantic-ai may pass either the raw text (str)
    or the already-parsed `QueryPlan` object into process hooks. Handle both.
    """
    logger.info("Planner raw text output (validator) called")
    try:
        if isinstance(text_or_obj, str):
            logger.debug("Raw planner text: %s", text_or_obj[:2000])
        else:
            # Attempt to serialize parsed object for inspection
            if hasattr(text_or_obj, "model_dump_json"):
                logger.debug(
                    "Planner produced parsed object (truncated): %s",
                    text_or_obj.model_dump_json()[:2000],
                )
            else:
                logger.debug("Planner produced object: %s", str(text_or_obj)[:2000])
    except Exception:
        logger.exception("Error while logging planner raw output")

    return text_or_obj


@planner_agent.output_validator
def planner_structured_validator(ctx: RunContext, plan: QueryPlan) -> QueryPlan:
    """Inspect and log the parsed `QueryPlan` object. If fields are missing, raise ModelRetry."""
    logger.info("Planner parsed output received")
    try:
        plan_dict = plan.model_dump()
        logger.debug("Parsed plan (all fields): %s", plan_dict)
    except Exception:
        logger.exception("Failed to dump parsed plan")

    # Check for extra fields that were stripped during parsing
    try:
        # Get the raw input that was validated
        if hasattr(plan, "__pydantic_extra__") and plan.__pydantic_extra__:
            logger.warning(
                "Model produced extra fields (ignored): %s", plan.__pydantic_extra__
            )
    except Exception:
        pass

    # Basic sanity checks to fail fast with a clear message
    if not plan.intent or not isinstance(plan.intent, str):
        logger.warning(
            "Parsed plan missing `intent` or it's invalid: %s",
            getattr(plan, "intent", None),
        )
        raise ModelRetry("Parsed plan missing required `intent` field.")

    return plan
