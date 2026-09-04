"""Centralised environment configuration via pydantic-settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        # .env is shared with docker-compose (POSTGRES_*, PGADMIN_*); ignore
        # anything that isn't an app setting instead of failing at import.
        extra="ignore",
    )

    # Postgres (ADR-0007: one cluster, two schemas, two roles).
    # The DSNs carry their own search_path (options=-csearch_path=…) so the
    # roles can resolve unqualified table names to their intended schema.
    pg_dsn: str = "postgresql://postgres:postgres@localhost:5433/fraud"
    reference_dsn: str = "postgresql://reference_readonly:reference_readonly@localhost:5433/fraud?options=-csearch_path%3Dreference"
    appstate_dsn: str = "postgresql://app_rw:app_rw@localhost:5433/fraud?options=-csearch_path%3Dappstate"
    run_timeout_s: int = 60
    # Hard cap on how long any single statement may run on the read-only
    # reference reader (spec: "enforced row cap and statement timeout,
    # regardless of what the model requested"). Applied per connection in
    # core/db.py via SET statement_timeout.
    readonly_statement_timeout_ms: int = 5000
    # LLM model + run budgets
    turn_wall_clock_s: int = 120

    # LLM (provider-agnostic; see app.common.model.get_model)
    llm_provider: str = "ollama"
    llm_model: str = ""
    llm_api_base: str = "http://localhost:11434"
    llm_api_key: str | None = None

    # Frontend origins for CORS: JSON list, comma-separated, or empty
    origins: str = ""

    # Logging
    log_level: str = "INFO"

    # Langfuse tracing
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str | None = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        """Parse ``origins`` into a list (empty string yields an empty list)."""
        text = self.origins.strip()
        if not text:
            return []
        if text.startswith("["):
            return cast(list[str], json.loads(text))
        return [item.strip() for item in text.split(",") if item.strip()]


settings = Settings()
