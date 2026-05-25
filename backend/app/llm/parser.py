import json
from typing import Any

from app.llm.schemas import SQLResponse, Insight, FraudRule


def repair_json(content: str) -> str:
    """Best-effort JSON repair stub. Replace with robust implementation later."""
    try:
        json.loads(content)
        return content
    except Exception:
        return json.dumps({})


def parse_sql_response(content: str) -> SQLResponse | None:
    try:
        data = json.loads(content)
        return SQLResponse.model_validate(data)
    except Exception:
        return None
