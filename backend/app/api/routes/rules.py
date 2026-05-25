from fastapi import APIRouter
from pydantic import BaseModel
from app.domain.rules.service import generate_rule

router = APIRouter()


class RuleRequest(BaseModel):
    sql: str
    insight: str
    results: list[dict]


@router.post("/rules")
def rules_route(body: RuleRequest):
    return generate_rule(sql=body.sql, insight=body.insight, results=body.results)
