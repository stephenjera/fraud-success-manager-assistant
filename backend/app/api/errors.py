"""The one error shape and its stable codes (ADR-0011 convention).

Every 4xx/5xx body is ``{"error": {"code", "message", "details"?}}``. The codes
are the frozen contract (``api-contract.md``); the frontend has one path for them.
``ApiError`` is raised from the routers and translated here, so no route hand-rolls a
status+body pair — the shape cannot drift.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Stable, machine-readable codes the contract promises (api-contract.md).
RUN_TIMEOUT = "RUN_TIMEOUT"
SQL_REJECTED = "SQL_REJECTED"
RULE_ILLEGAL_TRANSITION = "RULE_ILLEGAL_TRANSITION"
STATE_NOT_FOUND = "STATE_NOT_FOUND"
LLM_ERROR = "LLM_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"

# code → default HTTP status (a route may override on throw).
_CODE_STATUS: dict[str, int] = {
    RUN_TIMEOUT: 408,
    SQL_REJECTED: 400,
    RULE_ILLEGAL_TRANSITION: 409,
    STATE_NOT_FOUND: 404,
    LLM_ERROR: 502,
    INTERNAL_ERROR: 500,
}


class ApiError(Exception):
    """A routed failure: a frozen ``code`` plus a human message and optional details."""

    __slots__ = ("code", "message", "details", "status")

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None, status: int | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        self.status = status if status is not None else _CODE_STATUS.get(code, 500)

    def body(self) -> dict[str, Any]:
        """The contract's single error envelope."""
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def not_found(message: str, *, details: dict[str, Any] | None = None) -> ApiError:
    """A ``STATE_NOT_FOUND`` (404) for a missing resource."""
    return ApiError(STATE_NOT_FOUND, message, details=details)


def sql_rejected(reason: str, offending_sql: str) -> ApiError:
    """A ``SQL_REJECTED`` (400) carrying the offending SQL in ``details``."""
    return ApiError(SQL_REJECTED, reason, details={"offending_sql": offending_sql})


def register(app: FastAPI) -> None:
    """Wire the handlers: ``ApiError``, validation, and the catch-all — all one shape."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content=ApiError(INTERNAL_ERROR, "Invalid request body.", details={"errors": exc.errors()}).body())

    @app.exception_handler(Exception)
    async def _internal(_: Request, exc: Exception) -> JSONResponse:
        detail = exc.args[0] if exc.args and isinstance(exc.args[0], str) else type(exc).__name__
        return JSONResponse(status_code=500, content=ApiError(INTERNAL_ERROR, "Unexpected server error.", details={"error": detail}).body())
