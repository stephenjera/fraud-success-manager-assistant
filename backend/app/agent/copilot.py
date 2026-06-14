from __future__ import annotations

import re
from typing import Final

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.prompts.builder import build_copilot_prompt
from app.agent.types import AgentDependencies
from app.api.schemas import SQLResponse
from app.config import settings
from app.database import SCHEMA_DDL
from app.logger import get_logger

logger = get_logger("fsm_copilot")


UNIFIED_ALIASES: Final[set[str]] = {"t", "fl", "c", "u", "m", "mc"}

ALIAS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b([a-z_][a-z0-9_]*)\.",
    re.IGNORECASE,
)


def normalize_sql(sql: str) -> str:
    return sql.replace(";", "").strip()


def strip_where_clause(sql: str) -> str:
    return re.sub(r"^\s*WHERE\s+", "", sql.strip(), flags=re.IGNORECASE)


def validate_explore_sql(ctx: RunContext[AgentDependencies], sql: str) -> list[str]:
    errors: list[str] = []

    if not sql or not sql.strip():
        return ["explore_sql is empty"]

    clean_sql = normalize_sql(sql)
    is_full_query = clean_sql.upper().startswith("SELECT")

    if is_full_query:
        test_query = f"SELECT * FROM ({clean_sql}) LIMIT 0;"
    else:
        predicate = strip_where_clause(clean_sql)
        test_query = f"""
            SELECT 1
            FROM transactions t
            LEFT JOIN fraud_labels fl ON t.id = fl.transaction_id
            LEFT JOIN cards c ON t.card_id = c.id
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN merchants m ON t.merchant_id = m.id
            LEFT JOIN mcc_codes mc ON m.mcc = mc.mcc
            WHERE {predicate}
            LIMIT 0;
        """

    try:
        ctx.deps.db.execute(test_query)
    except Exception as exc:
        errors.append(f"explore_sql failed: {exc}")

    return errors


def validate_rule_predicate(
    ctx: RunContext[AgentDependencies],
    predicate_sql: str,
) -> list[str]:
    errors: list[str] = []

    if not predicate_sql or not predicate_sql.strip():
        return ["rule_predicate must be provided when is_exploratory_only=false"]

    predicate = strip_where_clause(predicate_sql)

    used_aliases = set(ALIAS_PATTERN.findall(predicate))
    invalid_aliases = used_aliases - UNIFIED_ALIASES

    if invalid_aliases:
        errors.append(f"Invalid aliases: {invalid_aliases}. Allowed: {UNIFIED_ALIASES}")
        return errors

    test_query = f"""
        SELECT 1
        FROM transactions t
        LEFT JOIN fraud_labels fl ON t.id = fl.transaction_id
        LEFT JOIN cards c ON t.card_id = c.id
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN merchants m ON t.merchant_id = m.id
        LEFT JOIN mcc_codes mc ON m.mcc = mc.mcc
        WHERE {predicate}
        LIMIT 0;
    """

    try:
        ctx.deps.db.execute(test_query)
    except Exception as exc:
        errors.append(f"rule_predicate failed: {exc}")

    return errors


fsm_copilot_agent = Agent(
    model=settings.LLM_MODEL,
    output_type=SQLResponse,
)

logger.info("FSM Co-Pilot Agent initialized with model: %s", settings.LLM_MODEL)


@fsm_copilot_agent.system_prompt
def system_prompt(ctx: RunContext[AgentDependencies]) -> str:
    history = getattr(ctx, "message_history", None)

    execution_context = ctx.deps.execution_context

    return build_copilot_prompt(
        schema=SCHEMA_DDL,
        message_history=history or [],
        current_rule_state=ctx.deps.current_rule_state,
        user_prompt=getattr(ctx, "prompt", ""),
        execution_context=execution_context,
    )


@fsm_copilot_agent.tool
def search_merchant_names(
    ctx: RunContext[AgentDependencies],
    search_term: str,
) -> list[str]:
    """Lookup merchant names safely using parameterized query."""
    logger.info("search_merchant_names called")

    query = """
        SELECT DISTINCT name
        FROM merchants
        WHERE name ILIKE ?
        LIMIT 5;
    """

    param = f"%{search_term.strip()}%"

    cursor = ctx.deps.db.execute(query, [param])
    results = [row[0] for row in cursor.fetchall()]

    logger.debug("Merchant search results: %s", results)
    return results


@fsm_copilot_agent.output_validator
def validate_sql_sandbox(
    ctx: RunContext[AgentDependencies],
    result: SQLResponse,
) -> SQLResponse:
    logger.info("Validating SQLResponse")

    errors: list[str] = []

    errors.extend(validate_explore_sql(ctx, result.explore_sql))

    if not result.is_exploratory_only:
        errors.extend(validate_rule_predicate(ctx, result.rule_predicate or ""))

    if errors:
        logger.debug("Validation errors: %s", errors)
        raise ModelRetry("Validation failed:\n- " + "\n- ".join(errors))

    logger.info("MODEL_OUTPUT_RAW | sql=%s", result.explore_sql)
    logger.info("MODEL_OUTPUT_RULE | predicate=%s", result.rule_predicate)
    logger.info("MODEL_MODE | exploratory_only=%s", result.is_exploratory_only)

    logger.info(
        "EXECUTION_CONTEXT_AVAILABLE | has_context=%s",
        ctx.deps.execution_context is not None,
    )

    return result
