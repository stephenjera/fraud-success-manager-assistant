from app.llm.client import LLMService


def generate_rule(sql: str, insight: str, results: list[dict]):
    """Generate a FraudRule using the existing LLM service."""
    llm = LLMService()
    return llm.generate_rule(sql=sql, insight=insight, results=results)
