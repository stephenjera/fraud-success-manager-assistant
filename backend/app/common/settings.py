"""Centralised environment configuration via pydantic-settings."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
    )

    # Data
    db_path: str = ""

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
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]


settings = Settings()
