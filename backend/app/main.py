from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import execute, explore, rules, sessions
from app.config import (
    on_shutdown,
    on_startup,
    run_shutdown_hooks,
    run_startup_hooks,
    settings,
)
from app.logger import get_logger

logger = get_logger("startup")

app = FastAPI(title="Fraud Success Manager Assistant API Server")

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=settings.ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@on_startup
def _init_sessions_db() -> None:
    """Initialise persistent session database and expire stale sessions."""
    from app.api.services import session_store
    session_store.init_db()
    session_store.expire_old_sessions()
    logger.info("Session persistence initialised")


@on_startup
def _init_observability() -> None:
    """Initialise Langfuse and enable pydantic-ai OTel instrumentation."""
    from pydantic_ai import Agent
    from pydantic_ai.models.instrumented import InstrumentationSettings

    from app.observability import init_langfuse

    client = init_langfuse()
    if client:
        Agent.instrument_all(
            instrument=InstrumentationSettings(
                version=4,
                include_content=True,
            ),
        )
        logger.info("Observability enabled — Langfuse + pydantic-ai OTel instrumentation active")
    else:
        logger.info("Observability disabled — Langfuse not configured")


@on_shutdown
def _shutdown_observability() -> None:
    """Flush and close Langfuse client."""
    from app.observability import flush_langfuse
    flush_langfuse()
    logger.info("Observability shutdown complete")


@app.on_event("startup")
def _startup() -> None:
    logger.info("Running startup hooks...")
    run_startup_hooks()
    logger.info("Startup complete")


@app.on_event("shutdown")
def _shutdown() -> None:
    logger.info("Running shutdown hooks...")
    run_shutdown_hooks()
    logger.info("Shutdown complete")


# Register routers
app.include_router(explore.router, prefix="/api")
app.include_router(execute.router, prefix="/api")
app.include_router(rules.router, prefix="/api/rules")
app.include_router(sessions.router, prefix="/api")

