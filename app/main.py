"""FastAPI server for fraud analysis."""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pipeline import run_pipeline
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Fraud Success Manager")

logger = logging.getLogger(__name__)

# Add CORS middleware
app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


class AnalysisRequest(BaseModel):
    """Request model for fraud analysis."""

    question: str = Field(..., description="The fraud analysis question")


class AnalysisResponse(BaseModel):
    """Response model for fraud analysis."""

    sql: str
    results: list[Any] | None
    insight: str | None
    rule: str | None
    evaluation: dict[str, Any]


@app.post("/analyze")
def analyze(payload: AnalysisRequest) -> AnalysisResponse:
    """Analyze a fraud question and return SQL, results, insights, and rules."""
    logger.info("Analyze request received: %s", payload.question)
    try:
        result = run_pipeline(payload.question)
        return AnalysisResponse(**result)
    except Exception as e:
        logger.exception("Pipeline failed for question: %s", payload.question)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {e!s}",
        ) from e


@app.get("/")
def root() -> FileResponse:
    """Serve the main HTML page."""
    return FileResponse(str(static_path / "index.html"))
