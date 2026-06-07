"""SQL generation agent."""

import re

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.prompts.builder import build_generator_prompt
from app.agent.types import AgentDependencies
from app.config import settings
from app.database import SCHEMA_DDL
from app.logger import get_logger
from app.schemas import SQLResponse

logger = get_logger("sql_generator")


sql_generator_agent = Agent(
    model=settings.LLM_MODEL,
    output_type=SQLResponse,
)


@sql_generator_agent.system_prompt
def generator_prompt(_: RunContext) -> str:
    return build_generator_prompt(SCHEMA_DDL)


@sql_generator_agent.tool
def search_merchant_names(
    ctx: RunContext[AgentDependencies],
    search_term: str,
) -> list[str]:
    logger.info("search_merchant_names called")
    logger.debug("search_term: %s", search_term)

    safe_term = search_term.strip().replace("'", "''")
    logger.debug("safe_term: %s", safe_term)

    query = f"""
        SELECT DISTINCT name
        FROM merchants
        WHERE name ILIKE '%{safe_term}%'
        LIMIT 5;
        """
    logger.debug("Executing merchant search SQL: %s", query.replace("\n", " "))

    cursor = ctx.deps.db.execute(query)
    results = [row[0] for row in cursor.fetchall()]
    logger.debug("Merchant search results: %s", results)

    logger.info("search_merchant_names completed, %d results", len(results))
    return results


@sql_generator_agent.output_validator
def validate_sql_sandbox(
    ctx: RunContext[AgentDependencies],
    result: SQLResponse,
) -> SQLResponse:
    logger.info("Validating dual-output SQLResponse")
    logger.debug("Is exploratory only: %s", result.is_exploratory_only)
    logger.debug("Explore SQL present: %s", bool(result.explore_sql))
    logger.debug("Rule predicate present: %s", bool(result.rule_predicate))

    # Define the unified alias environment that is always available
    UNIFIED_ALIASES = {"t", "fl", "c", "u", "m", "mc"}
    alias_descriptions = {
        "t": "transactions",
        "fl": "fraud_labels",
        "c": "cards",
        "u": "users",
        "m": "merchants",
        "mc": "mcc_codes",
    }

    errors_collected = []

    # --- Validation Strategy 1: Always validate explore_sql ---
    explore_sql = result.explore_sql
    if not explore_sql or not explore_sql.strip():
        errors_collected.append("explore_sql is empty or None")
    else:
        clean_explore_sql = explore_sql.replace(";", "").strip()
        logger.debug("Validating explore_sql (truncated): %s", clean_explore_sql[:1000])

        # Determine if we're looking at a full query or fragment
        is_full_query = bool(re.match(r"^\s*SELECT", clean_explore_sql, re.IGNORECASE))

        if is_full_query:
            # Case A: Standard full dashboard query sequence
            test_query_explore = f"SELECT * FROM ({clean_explore_sql}) LIMIT 0;"
        else:
            # Treat as WHERE clause fragment
            logger.warning(
                "explore_sql appears to be a fragment, not a full query. Wrapping in harness."
            )
            predicate = re.sub(
                r"^\s*WHERE\s+", "", clean_explore_sql, flags=re.IGNORECASE
            )
            test_query_explore = f"""
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
            logger.debug(
                "Sandbox execution check for explore_sql: %s",
                test_query_explore.replace("\n", " "),
            )
            ctx.deps.db.execute(test_query_explore)
            logger.info("explore_sql validation passed")
        except Exception as db_error:
            logger.exception("explore_sql validation failed: %s", db_error)
            errors_collected.append(
                f"explore_sql validation failed: {str(db_error)}\nAttempted SQL: {clean_explore_sql[:500]}"
            )

    # --- Validation Strategy 2: Validate rule_predicate only if NOT exploratory_only ---
    if not result.is_exploratory_only:
        rule_predicate = result.rule_predicate
        if rule_predicate and rule_predicate.strip():
            clean_predicate = rule_predicate.replace(";", "").strip()
            logger.debug("Validating rule_predicate (truncated): %s", clean_predicate[:1000])

            # Clean off explicit leading WHERE if hallucinated
            predicate = re.sub(
                r"^\s*WHERE\s+", "", clean_predicate, flags=re.IGNORECASE
            )

            # Extract all table aliases used in the predicate (simple regex scan)
            # Look for patterns like t., fl., c., u., m., mc.
            alias_pattern = r"\b([a-z_]\w*)\."
            used_aliases = set(re.findall(alias_pattern, predicate))
            logger.debug("Aliases found in rule_predicate: %s", used_aliases)

            # Cross-validation: ensure predicate uses only unified aliases
            invalid_aliases = used_aliases - UNIFIED_ALIASES
            if invalid_aliases:
                error_msg = (
                    f"rule_predicate uses invalid table aliases: {invalid_aliases}\n\n"
                    f"CRITICAL RETRY INSTRUCTION:\n"
                    f"You are generating a raw WHERE clause predicate fragment for a pre-defined backtester environment.\n"
                    f"The following table aliases are ALREADY joined and fully available in scope—do NOT write independent "
                    f"subqueries, re-join these tables, or introduce new table aliases (like t2, mc2, m2):\n"
                )
                for alias in sorted(UNIFIED_ALIASES):
                    error_msg += f"  - {alias:<3} : {alias_descriptions[alias]}\n"
                error_msg += f"Please rewrite your predicate to use these existing aliases directly (e.g., t.errors = 'Bad PIN' AND mc.name = '...')."
                errors_collected.append(error_msg)
                logger.error("Invalid aliases detected: %s", invalid_aliases)
            else:
                # Wrap in the exact 6-table harness and validate compilation
                test_query_predicate = f"""
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
                    logger.debug(
                        "Sandbox execution check for rule_predicate: %s",
                        test_query_predicate.replace("\n", " "),
                    )
                    ctx.deps.db.execute(test_query_predicate)
                    logger.info("rule_predicate validation passed")
                except Exception as db_error:
                    logger.exception("rule_predicate validation failed: %s", db_error)
                    errors_collected.append(
                        f"rule_predicate validation failed: {str(db_error)}\nAttempted WHERE clause: {clean_predicate[:500]}"
                    )
        else:
            logger.info(
                "No rule_predicate to validate (is_exploratory_only=false but predicate is empty)"
            )
    else:
        logger.info("Skipping rule_predicate validation (is_exploratory_only=true)")

    # --- Raise all collected errors at once ---
    if errors_collected:
        full_error = "\n\n---\n\n".join(errors_collected)
        logger.error("SQLResponse validation failed with errors: %s", full_error)
        raise ModelRetry(full_error) from None

    logger.info("SQLResponse validation passed: all outputs verified")
    return result
