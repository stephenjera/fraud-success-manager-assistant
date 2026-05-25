from fastapi import APIRouter

from app.api.schemas import QueryRequest, QueryResponse
from app.domain.exploration.service import explore

router = APIRouter()


@router.post("/explore")
def explore_route(request: QueryRequest) -> QueryResponse:
    schema = (request.__dict__.get("schema") or None)  # optional: allow passing schema
    # For now, reuse the domain exploration service
    return explore(question=request.question, schema=schema or "")
