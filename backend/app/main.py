import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import explore as explore_router
from app.api.routes import health as health_router
from app.api.routes import insights as insights_router
from app.api.routes import investigation as investigation_router
from app.api.routes import rules as rules_router
from app.api.schemas import QueryRequest, QueryResponse
from app.core.config import settings
from app.core.logger import get_logger, request_id_ctx
from app.core.validators import SQLValidationError
from app.db.schema_loader import load_schema
from app.services.pipeline import run_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up")

    yield

    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=settings.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = get_logger(__name__)


@app.middleware("http")
async def add_request_id_middleware(request, call_next):
    """Attach a per-request UUID to the logging context and log request lifecycle."""
    request_id = str(uuid.uuid4())
    token = request_id_ctx.set(request_id)

    logger.info("Request start: %s %s", request.method, request.url.path)

    try:
        response = await call_next(request)

        logger.info(
            "Request end: %s %s %s",
            request.method,
            request.url.path,
            getattr(response, "status_code", "-"),
        )

        return response

    finally:
        request_id_ctx.reset(token)


@app.post("/query")
def query_endpoint(request: QueryRequest) -> QueryResponse:
    try:
        schema = load_schema()

        return run_pipeline(question=request.question, schema=schema)

    except SQLValidationError as exc:
        logger.warning("Validation failed: %s", str(exc))

        return QueryResponse(
            sql=None,
            explanation=None,
            confidence=None,
            results=None,
            error=f"SQL validation error: {str(exc)}",
        )

    except Exception as exc:
        logger.exception("Query failed: %s")

        return QueryResponse(
            sql=None,
            explanation=None,
            confidence=None,
            results=None,
            error=str(exc),
        )


# Mount routers
app.include_router(explore_router.router, prefix="/api")
app.include_router(rules_router.router, prefix="/api")
app.include_router(insights_router.router, prefix="/api")
app.include_router(health_router.router, prefix="/api")
app.include_router(investigation_router.router, prefix="/api")
