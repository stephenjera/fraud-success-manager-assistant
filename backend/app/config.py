"""Configuration management for the core application."""

from collections.abc import Callable

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a .env file."""

    LLM_MODEL: str = "ollama:qwen3.6:27b-128k-agent"
    LLM_API_BASE: str = "http://localhost:11434"
    ORIGINS: list[str] = ["http://localhost:5173"]
    LOG_LEVEL: str = "INFO"
    QUERY_MAX_ROWS: int = 10000
    QUERY_TIMEOUT_SECONDS: int = 30
    FRAUD_COST: float = 500.0
    FP_COST: float = 50.0
    SESSION_TTL_HOURS: int = 24
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "http://localhost:3000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def langfuse_enabled(self) -> bool:
        """Whether both Langfuse keys are configured."""
        return self.LANGFUSE_PUBLIC_KEY is not None and self.LANGFUSE_SECRET_KEY is not None


settings = Settings()

# Global application hooks
_startup_hooks: list[Callable] = []
_shutdown_hooks: list[Callable] = []


def on_startup(hook: Callable) -> Callable:
    """Register a function to run on application startup."""
    _startup_hooks.append(hook)
    return hook


def on_shutdown(hook: Callable) -> Callable:
    """Register a function to run on application shutdown."""
    _shutdown_hooks.append(hook)
    return hook


def run_startup_hooks() -> None:
    """Execute all registered startup hooks."""
    for hook in _startup_hooks:
        hook()


def run_shutdown_hooks() -> None:
    """Execute all registered shutdown hooks."""
    for hook in _shutdown_hooks:
        hook()
