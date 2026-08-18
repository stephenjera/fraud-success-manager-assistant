"""FastAPI application entrypoint for the Fraud Insight & Rule Copilot backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.observability import flush, is_configured
from app.common.settings import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Flush pending observability events on shutdown."""
    yield
    flush()


app = FastAPI(
    title="Fraud Insight & Rule Copilot API",
    version="0.1.0",
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["health"])
def ready() -> dict[str, object]:
    """Readiness probe: report the configured state of backend dependencies."""
    return {
        "ready": bool(settings.llm_model),
        "llm": {
            "configured": bool(settings.llm_model),
            "provider": settings.llm_provider,
        },
        "langfuse": {"configured": is_configured()},
    }
