import os

from app.config import settings

os.environ.setdefault("OLLAMA_BASE_URL", settings.LLM_API_BASE + "/v1")
