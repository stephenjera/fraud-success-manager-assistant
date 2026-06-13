"""
Unified FSM Co-Pilot Agent (Single-Agent Architecture).

This agent:
- Consumes full conversational + system state
- Generates BOTH exploration SQL and rule predicates
- Validates outputs against live DuckDB
- Retries automatically on failure
"""

from __future__ import annotations

import re

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.prompts.builder import build_copilot_prompt
from app.agent.types import AgentDependencies
from app.config import settings
from app.database import SCHEMA_DDL
from app.logger import get_logger
from app.schemas import SQLResponse

logger = get_logger("fsm_copilot")


# --- Agent Definition ---
fsm_copilot_agent = Agent(
    model=settings.LLM_MODEL,
    output_type=SQLResponse,
)

logger.info("FSM Co-Pilot Agent initialized with model: %s", settings.LLM_MODEL)


@fsm_copilot_agent.system_prompt
def system_prompt(ctx: RunContext[AgentDependencies]) -> str:
    """Safe runtime-compatible system prompt builder."""
    history = getattr(ctx, "message_history", None)

    return build_copilot_prompt(
        schema=SCHEMA_DDL,
        message_history=history or [],
        current_rule_state=ctx.deps.current_rule_state,
        user_prompt=getattr(ctx, "prompt", ""),
    )


# --- Tool: Merchant Name Search ---
@fsm_copilot_agent.tool
def search_merchant_names(
    ctx: RunContext[AgentDependencies],
    search_term: str,
) -> list[str]:
    """
    Lookup merchant names to avoid hallucinated values in SQL generation.
    """
    logger.info("search_merchant_names called")
    safe_term = search_term.strip().replace("'", "''")

    query = f"""
        SELECT DISTINCT name
        FROM merchants
        WHERE name ILIKE '%{safe_term}%'
        LIMIT 5;
    """

    cursor = ctx.deps.db.execute(query)
    results = [row[0] for row in cursor.fetchall()]

    logger.debug("Merchant search results: %s", results)
    return results


# --- Output Validator (UNCHANGED CORE, SLIGHTLY CLEANED) ---
@fsm_copilot_agent.output_validator
def validate_sql_sandbox(
    ctx: RunContext[AgentDependencies],
    result: SQLResponse,
) -> SQLResponse:
    """
    Validate SQL execution and rule predicate correctness using live DB.
    Retries automatically on failure.
    """
    logger.info("Validating SQLResponse")

    UNIFIED_ALIASES = {"t", "fl", "c", "u", "m", "mc"}

    alias_descriptions = {
        "t": "transactions",
        "fl": "fraud_labels",
        "c": "cards",
        "u": "users",
        "m": "merchants",
        "mc": "mcc_codes",
    }

    errors: list[str] = []

    # --- Validate explore_sql ---
    if not result.explore_sql or not result.explore_sql.strip():
        errors.append("explore_sql is empty")
    else:
        clean_sql = result.explore_sql.replace(";", "").strip()

        is_full_query = bool(re.match(r"^\s*SELECT", clean_sql, re.IGNORECASE))

        if is_full_query:
            test_query = f"SELECT * FROM ({clean_sql}) LIMIT 0;"
        else:
            predicate = re.sub(r"^\s*WHERE\s+", "", clean_sql, flags=re.IGNORECASE)
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

    # --- Validate rule_predicate ---
    if not result.is_exploratory_only:
        if not result.rule_predicate or not result.rule_predicate.strip():
            errors.append(
                "rule_predicate must be provided when is_exploratory_only=false"
            )
        else:
            predicate = re.sub(
                r"^\s*WHERE\s+", "", result.rule_predicate.strip(), flags=re.IGNORECASE
            )

            alias_pattern = r"\b([a-z_]\w*)\."
            used_aliases = set(re.findall(alias_pattern, predicate))

            invalid_aliases = used_aliases - UNIFIED_ALIASES
            if invalid_aliases:
                error_msg = (
                    f"Invalid aliases: {invalid_aliases}\nAllowed: {UNIFIED_ALIASES}\n"
                )
                errors.append(error_msg)
            else:
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

    # --- Raise retry if needed ---
    if errors:
        raise ModelRetry("\n\n".join(errors))

    return result
