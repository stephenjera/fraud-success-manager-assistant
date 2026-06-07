import os
from app.config import settings

os.environ.setdefault("OLLAMA_BASE_URL", settings.OLLAMA_BASE_URL)
