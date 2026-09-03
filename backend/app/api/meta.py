"""Meta routes: version, health, readiness, and the reflected reference schema."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from fastapi import APIRouter

from app.common import observability
from app.common.settings import settings

router = APIRouter(tags=["meta"])

_BUILT_AT: str = datetime.now(timezone.utc).isoformat()


def _git_sha() -> str:
    """Best-effort HEAD sha (empty when not a git checkout)."""
    root = Path(__file__).resolve().parents[3]  # api/ app/ backend/ → repo root
    head = root / ".git" / "HEAD"
    try:
        text = head.read_text().strip()
        if text.startswith("ref:"):
            ref = text.split(" ", 1)[1].strip()
            return (root / ".git" / ref).read_text().strip()[:12]
        return text[:12]
    except Exception:  # noqa: BLE001 - version route must never fail
        return ""


@router.get("/v1/meta/version")
def version() -> dict[str, str]:
    """``{version, git_sha, built_at}`` — the cheap low-cost meta (ADR-0012)."""
    return {"version": "0.1.0", "git_sha": _git_sha(), "built_at": _BUILT_AT}


@router.get("/v1/health")
def health() -> dict[str, str]:
    """Liveness — always ``{"status": "ok"}``; no dependencies touched."""
    return {"status": "ok"}


@router.get("/v1/health/ready")
def ready() -> dict[str, Any]:
    """The "is it demoable" probe: report the configured state of dependencies."""
    db_ok = bool(settings.reference_dsn and settings.appstate_dsn)
    return {
        "ready": bool(settings.llm_model) and db_ok,
        "llm": {"configured": bool(settings.llm_model), "provider": settings.llm_provider, "model": settings.llm_model},
        "db": {"configured": db_ok},
        "langfuse": {"configured": observability.is_configured()},
    }


@router.get("/v1/schema")
def schema() -> dict[str, Any]:
    """The reflected reference schema (tables, columns, types) — read of *reference* data."""
    con = psycopg.connect(settings.reference_dsn, autocommit=True)
    try:
        with con.cursor() as cur:
            cur.execute(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns WHERE table_schema = 'reference' "
                "ORDER BY table_name, ordinal_position"
            )
            cols = cur.fetchall()
    finally:
        con.close()
    tables: dict[str, list[dict[str, Any]]] = {}
    for t, c, d, null in cols:
        tables.setdefault(t, []).append({"column": c, "data_type": d, "nullable": null == "YES"})
    return {"dialect": "postgres", "schema": "reference", "tables": tables}
