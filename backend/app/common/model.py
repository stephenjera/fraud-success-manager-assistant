"""Provider-agnostic chat model loading.

Every agent calls :func:`get_model` instead of importing a provider-specific
chat model directly, so the deployment can switch providers (Ollama, Anthropic,
OpenAI, ...) by changing environment variables alone — no code changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.chat_models import init_chat_model

from app.common.settings import settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

# Providers that require an explicit API key (local providers are exempt).
_API_KEY_PROVIDERS: frozenset[str] = frozenset({"anthropic", "openai", "google_genai"})


def get_model(**kwargs: Any) -> BaseChatModel:
    """Load the configured chat model via LangChain's ``init_chat_model``.

    Provider and model come from ``settings.llm_provider`` /
    ``settings.llm_model`` unless overridden via ``provider`` / ``model``
    keyword arguments. Ollama targets use ``settings.llm_api_base``.

    Args:
        **kwargs: Extra keyword arguments forwarded to ``init_chat_model``
            (e.g. ``temperature``), plus optional ``provider`` / ``model``
            overrides.

    Returns:
        A configured chat model implementing the LangChain Runnable
        interface.

    Raises:
        ValueError: If the LLM is not configured, or the resolved provider
            requires an API key that is not set.
    """
    provider: str = kwargs.pop("provider", None) or settings.llm_provider
    model: str = kwargs.pop("model", None) or settings.llm_model

    if not provider or not model:
        msg = (
            "LLM is not configured. Set LLM_PROVIDER and LLM_MODEL "
            "(see backend/.env.example)."
        )
        raise ValueError(msg)

    if (
        provider in _API_KEY_PROVIDERS
        and not settings.llm_api_key
        and "api_key" not in kwargs
    ):
        msg = f"LLM_API_KEY is required for provider '{provider}'."
        raise ValueError(msg)

    if provider == "ollama":
        # Ollama's native /api/chat (ChatOllama) rejects tool-continuation
        # transcripts on 0.33.x (tool_call `arguments` sent as a JSON string
        # fail to parse). Its OpenAI-compatible /v1 endpoint accepts the same
        # transcript with the stable OpenAI tool schema. Route Ollama through
        # the openai provider so ChatOpenAI targets `{base}/v1`.
        provider = "openai"
        kwargs.setdefault("base_url", settings.llm_api_base.rstrip("/") + "/v1")
        kwargs.setdefault("api_key", settings.llm_api_key or "ollama")

    return init_chat_model(model=model, model_provider=provider, **kwargs)
