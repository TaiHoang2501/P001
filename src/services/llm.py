from langchain_core.language_models import BaseChatModel

from src.config import get_settings


def get_fallback_llm() -> BaseChatModel | None:
    """A lighter model to answer when the main one fails (None when not configured)."""
    name = get_settings().llm_fallback_model
    return get_llm(name) if name else None


def get_llm(model: str | None = None, max_retries: int | None = None) -> BaseChatModel:
    """Chat model for the agent, from LLM_PROVIDER (openai | google); `model` overrides MODEL_NAME."""
    settings = get_settings()
    model = model or settings.llm_model
    retries = settings.llm_max_retries if max_retries is None else max_retries
    if settings.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=retries,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=retries,
    )
