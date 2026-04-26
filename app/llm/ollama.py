import json
import logging
import re

import requests
from llm.base import LLMClient

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"


class OllamaClient(LLMClient):
    def _call(self, prompt: str) -> str:
        logger.debug("Calling Ollama at %s (model=%s)", OLLAMA_URL, MODEL)
        response = requests.post(
            url=OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        raw = response.json().get("response", "")
        logger.debug("Ollama response (truncated): %s", raw[:200])
        return raw

    def _parse_json_field(self, raw: str, field: str, context: str = "") -> str:
        """Parse JSON field from LLM response with robust error handling."""
        logger.debug("Parsing JSON field '%s' for context '%s'", field, context)
        try:
            # Strip whitespace and try to find JSON in the response
            raw_stripped = raw.strip()
            if not raw_stripped:
                raise ValueError(f"Empty LLM response")

            # Try direct parse first
            return json.loads(raw_stripped)[field]
        except json.JSONDecodeError:
            # Try to extract JSON from the response if it's wrapped in text
            # Use proper escaping for the regex pattern
            pattern = r'\{[^{}]*"' + re.escape(field) + r'"[^{}]*\}'
            json_match = re.search(pattern, raw)
            if json_match:
                try:
                    return json.loads(json_match.group())[field]
                except json.JSONDecodeError:
                    logger.debug("Found JSON but failed to decode for field %s", field)
                    pass

            # If no JSON found, assume the entire response is the value
            # (LLM didn't wrap in JSON as instructed, but return it anyway)
            if raw_stripped and not raw_stripped.startswith("{"):
                logger.warning("LLM returned non-JSON response; using raw string for %s", context)
                return raw_stripped

            logger.error("Invalid LLM output for %s: %s", context, raw[:200])
            raise ValueError(f"Invalid LLM output for {context}. Response: {raw[:200]}")

    def generate_sql(self, question: str, schema: str) -> str:
        logger.info("Generating SQL for question: %s", question)
        prompt = f"""
        You are a SQL generator. Your ONLY output must be valid JSON.

        CRITICAL REQUIREMENTS:
        - Output ONLY a JSON object: {{"sql": "..."}}
        - No markdown, no explanation, no extra text
        - The SQL must be valid SQLite syntax
        - Do NOT use non-SQLite functions like `NOW()`; prefer `datetime('now')` or `date('now')`
        - Must use: SELECT ... FROM transactions JOIN fraud_labels ON transactions.id = fraud_labels.transaction_id

        Given Schema:
        {schema}

        REQUIREMENTS FOR THE SQL:
        1. Always use this exact join: 
           FROM transactions JOIN fraud_labels ON transactions.id = fraud_labels.transaction_id
        2. Both table names must appear in the query exactly as shown
        3. The join condition must be present: transactions.id = fraud_labels.transaction_id
        4. Analyze the question to determine what to SELECT, GROUP BY, or aggregate

        VALID EXAMPLE:
        {{"sql": "SELECT transactions.transaction_type, COUNT(*) as count, SUM(CASE WHEN fraud_labels.is_fraud THEN 1 ELSE 0 END) as fraud_count FROM transactions JOIN fraud_labels ON transactions.id = fraud_labels.transaction_id GROUP BY transactions.transaction_type"}}

        Question to answer:
        {question}
        """
        raw = self._call(prompt)
        return self._parse_json_field(raw, "sql", "SQL generation")

    def explain_insight(self, metrics: dict) -> str:
        logger.info("Generating insight from metrics")
        prompt = f"""
        You are a fraud analyst. Your ONLY output must be valid JSON.

        CRITICAL: Output only JSON, no explanation text.

        Metrics:
        {json.dumps(metrics)}

        OUTPUT FORMAT (you MUST follow this exactly):
        {{"insight": "Your analysis here"}}

        Example:
        {{"insight": "Online transactions have higher fraud rates"}}
        """
        raw = self._call(prompt)
        return self._parse_json_field(raw, "insight", "insight explanation")

    def generate_rule(self, insight: str, schema: str = "") -> str:
        logger.info("Generating rule from insight")
        schema_info = ""
        if schema:
            # Extract available columns from transactions table
            schema_info = """
        AVAILABLE COLUMNS in transactions table:
        - transaction_type (values: 'Chip Transaction', 'Online Transaction', 'Swipe Transaction')
        - amount_usd_cents (numeric)
        - errors (values: 'Bad CVV', 'Bad Card Number', 'Bad Expiration', 'Bad PIN', 'Bad Zipcode', 'Insufficient Balance', 'Technical Glitch')
        - date (DATETIME)
        - card_id (numeric, can JOIN to cards table)
        - merchant_id (numeric)

        JOINED TABLE (cards):
        - has_chip (BOOLEAN: TRUE/FALSE)
        """

        prompt = f"""
        Convert this insight into a SQL WHERE clause. Your ONLY output must be valid JSON.

        CRITICAL: Use ONLY columns that exist. Do NOT invent column names.

        {schema_info}

        Insight:
        {insight}

        OUTPUT FORMAT (you MUST follow this exactly):
        {{"rule": "column_name = 'value'"}}

        Examples of VALID rules:
        {{"rule": "transaction_type = 'Chip Transaction'"}}
        {{"rule": "amount_usd_cents > 100000"}}
        {{"rule": "c.has_chip = 1"}}
        """
        raw = self._call(prompt)
        return self._parse_json_field(raw, "rule", "rule generation")
