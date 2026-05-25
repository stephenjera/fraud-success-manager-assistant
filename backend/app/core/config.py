from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_PATH: str = "data/data.db"
    LLM_MODEL: str = "ollama_chat/granite4.1:3b"
    LLM_API_BASE: str = "http://localhost:11434"
    ORIGINS: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
