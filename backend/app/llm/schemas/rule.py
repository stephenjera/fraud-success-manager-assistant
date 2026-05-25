from pydantic import BaseModel


class FraudRule(BaseModel):
    rule_sql_where: str
    description: str
    confidence: float
    rationale: list[str]


__all__ = ["FraudRule"]
