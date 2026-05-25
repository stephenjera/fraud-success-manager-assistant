from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.insights.service import generate_insight

router = APIRouter()


class InsightRequest(BaseModel):
    question: str
    sql: str
    results: list[dict]


@router.post("/insights")
def insights_route(body: InsightRequest):
    return generate_insight(question=body.question, sql=body.sql, results=body.results)
