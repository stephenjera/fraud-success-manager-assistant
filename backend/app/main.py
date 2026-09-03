"""FastAPI entrypoint for the Fraud data copilot — the API is the product (ADR-0011).

Thin HTTP edge over the single grounded-Q&A agent. The routers carry the frozen
contract (``app/api/*``); the one error shape is registered once (``app.api.errors``);
CORS is pinned to the ``ORIGINS`` allowlist. The durable answer lives in ``appstate``;
the stream is only a view of it.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, errors, insights, meta, rules, runs
from app.common.observability import flush
from app.common.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Flush pending observability events on shutdown."""
    yield
    flush()


def create_app() -> FastAPI:
    """Build the ``/v1`` application (routers, error shape, CORS)."""
    app = FastAPI(title="Fraud data copilot API", version="0.1.0", lifespan=lifespan)

    app.include_router(meta.router)
    app.include_router(conversations.router)
    app.include_router(runs.router)
    app.include_router(insights.router)
    app.include_router(rules.router)

    errors.register(app)

    origins = settings.cors_origins
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    return app


app = create_app()
