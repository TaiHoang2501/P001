from langchain_core.language_models import BaseChatModel

from src.config import get_settings


def get_fallback_llm() -> BaseChatModel | None:
    """The model that answers when the main one fails (None when not configured).

    Same provider by default (a lighter model); LLM_FALLBACK_PROVIDER puts it on another one, e.g. Claude
    first and OpenRouter when Anthropic is down or out of credit.
    """
    settings = get_settings()
    name = settings.llm_fallback_model
    return get_llm(name, settings.llm_fallback_provider_name) if name else None


def get_llm(model: str | None = None, provider: str | None = None) -> BaseChatModel:
    """Chat model for the agent, from LLM_PROVIDER (openai | google | openrouter | groq | anthropic).

    `model` overrides MODEL_NAME and `provider` overrides LLM_PROVIDER.
    """
    settings = get_settings()
    provider = provider or settings.llm_provider
    model = model or settings.llm_model
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            # Current Claude models reject sampling parameters, so no temperature; thinking is always on and
            # effort sets how deep it goes
            temperature=None,
            max_tokens=8000,
            output_config={"effort": settings.llm_effort} if settings.llm_effort else None,
            # Claude binds its thinking to the conversation it was produced in (system prompt, tools, earlier
            # messages). The agent keeps conversations append-only; should one still change (a guest conversation
            # moved into the new account gets that buyer's prompt), the stale thinking is dropped instead of the
            # whole turn failing with a 400
            thinking={"type": "adaptive", "block_binding": {"prefix_mismatch_behavior": "drop_block"}},
            betas=["thinking-binding-controls-2026-08-01"],
            default_request_timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    from langchain_openai import ChatOpenAI

    if provider == "openrouter":
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

    if provider == "groq":
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
