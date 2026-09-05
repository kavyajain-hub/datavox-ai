from contextvars import ContextVar
from typing import Tuple, Optional
from langchain_openai import ChatOpenAI
from openai import OpenAI
from config.settings import get_settings

# Context variables to support per-request custom user API keys
user_api_key_ctx: ContextVar[Optional[str]] = ContextVar("user_api_key", default=None)
user_provider_ctx: ContextVar[Optional[str]] = ContextVar("user_provider", default=None)
user_model_ctx: ContextVar[Optional[str]] = ContextVar("user_model", default=None)


def set_request_llm_credentials(api_key: Optional[str] = None, provider: Optional[str] = None, model: Optional[str] = None):
    """Set request-scoped credentials for multi-tenant / user-provided API keys."""
    user_api_key_ctx.set(api_key.strip() if api_key and api_key.strip() else None)
    user_provider_ctx.set(provider.strip().lower() if provider and provider.strip() else None)
    user_model_ctx.set(model.strip() if model and model.strip() else None)


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """
    Instantiate a ChatOpenAI model configured for either Gemini or OpenAI.
    Prioritizes request-scoped user API keys over server environment variables.
    """
    settings = get_settings()

    # Check request context first, fallback to settings
    req_key = user_api_key_ctx.get()
    req_provider = user_provider_ctx.get()
    req_model = user_model_ctx.get()

    provider = req_provider or settings.llm_provider
    api_key = req_key or settings.active_api_key or "sk-mock-key-for-init"

    if provider == "gemini":
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = req_model or settings.gemini_model or "gemini-3.6-flash"
    else:
        base_url = settings.openai_base_url or None
        model = req_model or settings.openai_model or "gpt-4o-mini"

    if base_url:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature
        )
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature
    )


def get_embeddings_client() -> Tuple[OpenAI, str]:
    """
    Get an OpenAI client configured for embeddings.
    Prioritizes request-scoped user API keys.
    """
    settings = get_settings()
    req_key = user_api_key_ctx.get()
    req_provider = user_provider_ctx.get()

    provider = req_provider or settings.llm_provider
    api_key = req_key or settings.active_api_key or "sk-mock-key-for-init"

    if provider == "gemini":
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = settings.gemini_embedding_model or "gemini-embedding-001"
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        base_url = settings.openai_base_url or None
        model = settings.openai_embedding_model or "text-embedding-3-small"
        if base_url:
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key)

    return client, model
