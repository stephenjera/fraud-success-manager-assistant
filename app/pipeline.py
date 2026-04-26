import logging
from pathlib import Path
from typing import Any

from analytics import (
    compute_baseline,
    derive_insight_from_results,
    enrich_results_with_metrics,
    evaluate_rule_with_checks,
)
from llm.ollama import OllamaClient
from sql_executor import run_query
from validators import validate_sql, validate_sql_execution

logger = logging.getLogger(__name__)

ROOT_PATH = Path(__file__).parent.parent
SCHEMA_PATH = ROOT_PATH / "data" / "schema.sql"


def refine_rule(llm, insight: str, current_rule: str, evaluation: dict, schema: str):
    logger.info(" Refining rule due to poor performance")

    prompt = f"""
    You are a fraud expert improving a rule.

    The SQL schema must be followed exactly as you will not be able to produce valied SQL without it
    {schema}

    Current rule:
    {current_rule}

    Evaluation:
    Precision: {evaluation["precision"]}
    Recall: {evaluation["recall"]}
    Block rate: {evaluation["block_rate"]}

    Insight:
    {insight}

    The rule has too many false positives. Tighten it by adding constraints.

    CRITICAL:
    - Output ONLY JSON: {{"rule": "..."}}
    - Use valid SQL WHERE clause
    - Use existing columns only
    - Make the rule more specific

    Example:
    {{"rule": "transaction_type = 'Online Transaction' AND amount_usd_cents > 100000"}}
    """

    raw = llm._call(prompt)
    refined = llm._parse_json_field(raw, "rule", "rule refinement")

    logger.info(f" Refined rule candidate: {refined}")

    return refined


def run_pipeline(question: str) -> dict[str, Any]:
    logger.info(f" Starting pipeline for question: {question}")

    schema = open(SCHEMA_PATH).read()
    llm = OllamaClient()

    # Step 1: SQL generation
    sql = llm.generate_sql(question, schema)
    logger.info(f" Generated SQL: {sql}")

    # Step 2: validation
    valid, err = validate_sql(sql)
    if not valid:
        logger.error(f" SQL validation failed: {err}")
        return {
            "sql": sql,
            "results": None,
            "insight": None,
            "rule": None,
            "evaluation": {"error": f"SQL validation failed: {err}"},
        }

    valid, err = validate_sql_execution(sql)
    if not valid:
        logger.error(f" SQL execution validation failed: {err}")
        return {
            "sql": sql,
            "results": None,
            "insight": None,
            "rule": None,
            "evaluation": {"error": f"SQL execution validation failed: {err}"},
        }

    # Step 3: run query
    results = run_query(sql)
    logger.info(f" Query returned {len(results)} rows")

    if not results:
        logger.warning(" No results returned")
        return {
            "sql": sql,
            "results": [],
            "insight": "No results returned.",
            "rule": None,
            "evaluation": {},
        }

    # Step 4: baseline
    baseline = compute_baseline()
    logger.info(f" Baseline fraud rate: {baseline['fraud_rate']:.4f}")

    # Step 5: enrich results
    enriched_results = enrich_results_with_metrics(results, baseline)
    logger.info(f" Enriched results with fraud metrics")

    # Step 6: deterministic insight
    insight = derive_insight_from_results(enriched_results, baseline)
    logger.info(f" Derived insight: {insight}")

    # Step 7: initial rule
    top_row = enriched_results[0]

    rule = None
    if "transaction_type" in top_row:
        rule = f"transaction_type = '{top_row['transaction_type']}'"
        logger.info(f" Generated rule from data: {rule}")

    if not rule:
        rule = llm.generate_rule(insight, schema)
        logger.info(f" Generated rule via LLM: {rule}")

    # Step 8: evaluate
    evaluation = evaluate_rule_with_checks(rule)
    logger.info(
        f" Evaluation - Precision: {evaluation['precision']:.4f}, "
        f"Recall: {evaluation['recall']:.4f}, "
        f"Block Rate: {evaluation['block_rate']:.4f}, "
        f"Status: {evaluation['status']}"
    )

    # Step 9: refine if needed
    if evaluation["status"] in ["REVIEW", "REJECTED"]:
        try:
            refined_rule = refine_rule(llm, insight, rule, evaluation, schema)
            refined_eval = evaluate_rule_with_checks(refined_rule)

            logger.info(
                f" Refined Evaluation - Precision: {refined_eval['precision']:.4f}, "
                f"Recall: {refined_eval['recall']:.4f}, "
                f"Block Rate: {refined_eval['block_rate']:.4f}"
            )

            if refined_eval["precision"] > evaluation["precision"]:
                logger.info(" Refinement improved rule, adopting new rule")
                rule = refined_rule
                evaluation = refined_eval
                evaluation["note"] = "Rule was automatically refined"
            else:
                logger.info(" Refinement did not improve rule")

        except Exception as e:
            logger.error(f" Refinement failed: {e}")

    logger.info(" Pipeline complete")

    return {
        "sql": sql,
        "results": enriched_results,
        "insight": insight,
        "rule": rule,
        "evaluation": evaluation,
    }
