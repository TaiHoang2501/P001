import pytest

from src.config import get_settings
from src.services import llm_pricing


def test_built_in_claude_price_and_name_variants():
    assert llm_pricing.price_for("claude-sonnet-5-5") == (2.00, 10.00, 0.20)
    # Dated names and a provider prefix still find the price
    assert llm_pricing.price_for("claude-sonnet-5-5-20260901") == (2.00, 10.00, 0.20)
    assert llm_pricing.price_for("Claude-Haiku-5-5") == (0.10, 0.50, 0.01)
    assert llm_pricing.price_for("gemini-flash-lite-latest") is None
    assert llm_pricing.price_for(None) is None


def test_cost_counts_cache_reads_at_the_cache_price():
    # 1M in of which 600k cached, 100k out on Opus 5.5: 400k × $4 + 600k × $0.20 + 100k × $20
    assert llm_pricing.cost_usd("claude-opus-5-5", 1_000_000, 100_000, 600_000) == pytest.approx(1.6 + 0.12 + 2.0)
    assert llm_pricing.cost_usd("unknown-model", 1000, 100, 0) is None


def test_llm_prices_setting_adds_models(monkeypatch):
    # Keys match case-insensitively, and the traced "models/" prefix is ignored
    monkeypatch.setattr(get_settings(), "llm_prices", {"Gemini-X": (1.0, 2.0, 0.5)})
    assert llm_pricing.price_for("models/gemini-x") == (1.0, 2.0, 0.5)
