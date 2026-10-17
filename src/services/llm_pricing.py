"""Model prices for the developer dashboard's cost estimate (dev_metrics): USD per 1M tokens for input, output and
input read from the prompt cache.

Defaults cover the Claude models the code uses (Anthropic first-party API rates). Other models (Gemini, OpenRouter,
OpenAI) are priced only when the dev team sets LLM_PRICES, so the dashboard never shows a guessed number.
"""

from src.config import get_settings

# (input, output, cache read) USD per 1M tokens
DEFAULT_PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    # Prompts up to 100K tokens; cache read at the usual 0.1x of input
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}


def prices() -> dict[str, tuple[float, float, float]]:
    return {**DEFAULT_PRICES, **{k.lower(): v for k, v in get_settings().llm_prices.items()}}


def price_for(model: str | None) -> tuple[float, float, float] | None:
    """Price of a model as the trace names it. Also matches "models/gemini-…" and dated names such as
    "claude-sonnet-5-5-20260901" (longest known name it starts with)."""
    if not model:
        return None
    table = prices()
    name = model.lower().removeprefix("models/")
    if name in table:
        return table[name]
    matches = [key for key in table if name.startswith(key)]
    return table[max(matches, key=len)] if matches else None


def cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int, cache_read_tokens: int) -> float | None:
    """Estimated cost; None when the model has no price. Cache writes are billed a little above input but are not
    traced, so they count as plain input here."""
    price = price_for(model)
    if price is None:
        return None
    input_price, output_price, cache_price = price
    cached = min(cache_read_tokens, prompt_tokens)
    return ((prompt_tokens - cached) * input_price + cached * cache_price + completion_tokens * output_price) / 1e6
