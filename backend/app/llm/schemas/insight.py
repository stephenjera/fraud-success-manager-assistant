from pydantic import BaseModel


class Insight(BaseModel):
    summary: str
    risk_level: str
    key_findings: list[str]


__all__ = ["Insight"]
