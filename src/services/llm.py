from langchain_core.language_models import BaseChatModel

from src.config import get_settings


def get_fallback_llm() -> BaseChatModel | None:
    """A lighter model to answer when the main one fails (None when not configured)."""
    name = get_settings().llm_fallback_model
    return get_llm(name) if name else None


def get_llm(model: str | None = None) -> BaseChatModel:
    """Chat model for the agent, from LLM_PROVIDER (openai | google | openrouter | groq); `model` overrides MODEL_NAME."""
    settings = get_settings()
    model = model or settings.llm_model
    if settings.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    from langchain_openai import ChatOpenAI

    if settings.llm_provider == "openrouter":
        # OpenRouter speaks the OpenAI API; models are named "<vendor>/<model>", e.g. "openai/gpt-4o-mini"
        return ChatOpenAI(
            model=model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            # Shown on OpenRouter's dashboard, so usage can be told apart from other apps on the same account
            default_headers={"X-Title": "BookingBot"},
        )

    if settings.llm_provider == "groq":
        # Groq speaks the OpenAI API; models are named as Groq lists them, e.g. "openai/gpt-oss-120b"
        return ChatOpenAI(
            model=model,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
