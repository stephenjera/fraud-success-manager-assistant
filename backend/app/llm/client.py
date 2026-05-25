import json
from typing import Any

from litellm import completion

from app.core.config import settings
from app.core.logger import get_logger
from app.llm.prompt_loader import render_prompt
from app.llm.schemas.insight import Insight
from app.llm.schemas.rule import FraudRule
from app.llm.schemas.sql import SQLResponse

logger = get_logger(__name__)


def _extract_json_snippet(text: str) -> str | None:
    """Attempt to extract a JSON object from noisy LLM output.

    Returns the substring between the first `{` and the last `}` if found.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _is_safe_where_clause(where: str) -> bool:
    forbidden = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
    }
    up = where.upper()
    return all(kw not in up for kw in forbidden)


class LLMService:
    """Service responsible for interacting with the LLM with lightweight hardening."""

    def __init__(self, api_base: str | None = None, model: str | None = None) -> None:
        # Use values from pydantic BaseSettings when not explicitly provided
        self.api_base = api_base or settings.LLM_API_BASE
        self.model = model or settings.LLM_MODEL

    def generate_sql(self, question: str, schema: str) -> SQLResponse:
        """Generate SQL from natural language and parse defensively."""
        messages = render_prompt(
            name="sql",
            version="v1",
            context={
                "schema": schema,
                "question": question,
            },
        )

        logger.info("Generating SQL for question: %s", question)

        response = completion(
            model=self.model,
            messages=messages,
            response_format=SQLResponse,
            api_base=self.api_base,
            temperature=0,
        )

        content: str = response.choices[0].message.content

        # Log a truncated raw copy for debugging without leaking huge outputs
        logger.debug("Raw LLM response (truncated): %s", content[:1000])

        # First attempt strict pydantic parsing
        try:
            parsed = SQLResponse.model_validate_json(content)
            logger.info("Successfully parsed LLM SQL response")
            return parsed
        except Exception:
            logger.warning(
                "Strict SQLResponse parsing failed; attempting JSON extraction"
            )

        # Fallback: try to extract a JSON object from noisy text
        snippet = _extract_json_snippet(content)
        if snippet:
            try:
                parsed = SQLResponse.model_validate_json(snippet)
                logger.info("Parsed SQLResponse from extracted JSON snippet")
                return parsed
            except Exception:
                logger.exception("Parsing extracted SQL snippet failed")

        # Last resort: return a safe empty SQLResponse so caller can handle gracefully
        logger.error("Failed to parse SQLResponse from LLM; returning empty fallback")
        return SQLResponse(
            sql="", explanation="failed to parse LLM response", confidence=0.0
        )

    def safe_generate_sql(self, question: str, schema: str) -> SQLResponse:
        """Retry wrapper for robustness."""
        last_error: str | None = None

        for attempt in range(3):
            try:
                logger.info("LLM SQL attempt %d", attempt + 1)
                return self.generate_sql(question, schema)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("LLM SQL attempt failed: %s", last_error)

        logger.error("All LLM SQL attempts failed")
        raise RuntimeError(f"LLM failed after retries: {last_error}")

    def safe_parse_insight(self, content: str) -> Insight:
        """Robust parsing for LLM output."""

        try:
            # First try strict JSON
            data = json.loads(content)
            return Insight.model_validate(data)

        except Exception:
            # Fallback: log and degrade safely
            logger.warning("Insight parsing failed, using fallback")

            return Insight(
                summary="Insight generation failed",
                risk_level="unknown",
                key_findings=[],
            )

    def generate_insight(
        self,
        question: str,
        sql: str,
        results: list[dict[str, Any]],
    ) -> Insight:
        messages = render_prompt(
            name="insight",
            version="v1",
            context={
                "question": question,
                "sql": sql,
                "results": results,
            },
        )

        response = completion(
            model=self.model,
            messages=messages,
            response_format=Insight,
            api_base=self.api_base,
            temperature=0,
        )

        content = response.choices[0].message.content

        # Keep behavior same but log raw output for debugging
        logger.debug("Raw Insight response (truncated): %s", content[:1000])

        return self.safe_parse_insight(content)

    def generate_rule(
        self, sql: str, insight: str, results: list[dict[str, Any]]
    ) -> FraudRule:
        messages = render_prompt(
            name="rules",
            version="v1",
            context={
                "sql": sql,
                "insight": insight,
                "results": results,
            },
        )

        response = completion(
            model=self.model,
            messages=messages,
            response_format=FraudRule,
            api_base=self.api_base,
            temperature=0,
        )

        content = response.choices[0].message.content
        logger.debug("Raw Rule response (truncated): %s", content[:1000])

        # Try strict parse
        try:
            rule = FraudRule.model_validate_json(content)
        except Exception:
            logger.warning(
                "Strict FraudRule parsing failed; attempting JSON extraction"
            )
            snippet = _extract_json_snippet(content)
            if snippet:
                try:
                    rule = FraudRule.model_validate_json(snippet)
                except Exception:
                    logger.exception("Parsing extracted FraudRule snippet failed")
                    rule = None
            else:
                rule = None

        if not rule:
            logger.error(
                "Failed to parse FraudRule from LLM; returning safe empty rule"
            )
            return FraudRule(
                rule_sql_where="",
                description="failed to parse LLM response",
                confidence=0.0,
                rationale=["parse_failed"],
            )

        # Clean up loose syntax artifacts before evaluation
        where_clause = getattr(rule, "rule_sql_where", "").strip()

        # Log parsed rule details for debugging
        try:
            logger.info("Parsed FraudRule: confidence=%s where=%s description=%s", getattr(rule, 'confidence', None), where_clause, getattr(rule, 'description', None))
        except Exception:
            logger.exception("Failed logging parsed rule details")

        # Strip out loose "WHERE " prefixes if returned by the LLM
        if where_clause.upper().startswith("WHERE "):
            where_clause = where_clause[6:].strip()
            rule.rule_sql_where = where_clause

        # Safety checks on WHERE clause
        if (
            not where_clause
            or not _is_safe_where_clause(where_clause)
            or where_clause == "1=1"
        ):
            logger.warning(
                "Generated WHERE clause is unsafe, fallback or empty: %s", where_clause
            )
            return FraudRule(
                rule_sql_where="",
                description="unsafe or empty where clause",
                confidence=0.0,
                rationale=["unsafe_where"],
            )

        return rule


def get_llm_service(
    api_base: str | None = None, model: str | None = None
) -> LLMService:
    """Return an `LLMService` instance (compat helper).

    Accepts optional `api_base` and `model` overrides; otherwise uses
    values from `app.core.config.settings`.
    """
    return LLMService(api_base=api_base, model=model)
