"""Configuration management for the core application."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a .env file."""

    LLM_MODEL: str = "ollama:granite4.1:3b"
    OPENAI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    LOG_LEVEL: str = "INFO"

    class Config:
        """Pydantic configuration for the Settings class."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
