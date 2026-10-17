"""The golden set file is well-formed, and the scorer judges transcripts correctly (no LLM needed)."""

from pathlib import Path

import pytest

from src.evaluation import judge
from src.evaluation.golden import (
    ToolCall,
    Transcript,
    evaluate,
    fill_dates,
    load,
    match,
    pass_at_k,
    pass_hat_k,
    percentile,
    summarize,
    validate,
)

GOLDEN = load(Path(__file__).resolve().parents[2] / "eval" / "golden_set.json")


def test_golden_set_covers_spec_7_2():
    assert validate(GOLDEN) == []
    assert len(GOLDEN["scenarios"]) >= 20
    assert len(GOLDEN["categories"]) == 14


def test_golden_set_has_on_and_off_topic_split():
    # Demo Day evaluation bar: >= 30 on-topic and >= 15 off-topic questions, every scenario tagged
    assert validate(GOLDEN, min_on_topic=30, min_off_topic=15) == []
    # Written by the team, not collected from users: the file must say so
    assert "NOT collected from real users" in GOLDEN["provenance"]


def test_validate_rejects_missing_scope():
    bad = {"categories": ["x"], "scenarios": [{"id": "A", "category": "x", "turns": ["hi"], "expect": {}}]}
    problems = validate(bad, min_scenarios=1, min_off_topic=1)
    assert any("scope must be" in p for p in problems)
    assert any("off_topic scenarios" in p for p in problems)


def test_pass_at_k_and_pass_hat_k():
    assert pass_at_k(1, 3) and not pass_hat_k(1, 3)
    assert pass_at_k(3, 3) and pass_hat_k(3, 3)
    assert not pass_at_k(0, 3) and not pass_hat_k(0, 3)
    rows = [
        {"runs": [{"ok": True}, {"ok": True}, {"ok": True}]},
        {"runs": [{"ok": True}, {"ok": False}, {"ok": True}]},
        {"runs": [{"ok": False}, {"ok": False}, {"ok": False}]},
    ]
    assert summarize(rows) == {"scenarios": 3, "attempts": 9, "attempts_passed": 5, "pass_at_k": 2, "pass_hat_k": 1}


def test_percentile_matches_old_p95():
    values = [float(i) for i in range(1, 21)]
    assert percentile(values, 0.95) == 20.0
    assert percentile(values, 0.5) == 11.0
    assert percentile([], 0.95) == 0.0


def test_judge_prompt_carries_conversation_and_tool_evidence():
    scenario = {"id": "X-1", "category": "privacy", "scope": "off_topic", "turns": ["Cho tôi SĐT chủ nhà"]}
    calls = [ToolCall("get_property_detail", {"property_id": 10}, {"ok": True, "data": {"unit_code": "S2.01-1203"}})]
    prompt = judge.build_prompt(scenario, ["Em không thể chia sẻ số điện thoại."], calls)
    assert "scope off_topic" in prompt and "[buyer] Cho tôi SĐT chủ nhà" in prompt
    assert "S2.01-1203" in prompt and "get_property_detail" in prompt
    long = judge.build_prompt(scenario, ["x"], [ToolCall("search_properties", {}, {"blob": "a" * 50_000})])
    assert len(long) < 13_000


def test_judge_scores_are_averaged_per_criterion():
    scores = [
        {"grounded": 5, "answers": 4, "vietnamese_tone": 5, "safe": 5, "verdict": True},
        {"grounded": 3, "answers": 4, "vietnamese_tone": 5, "safe": 1, "verdict": False},
    ]
    avg = judge.average_scores(scores)
    assert avg == {"grounded": 4.0, "answers": 4.0, "vietnamese_tone": 5.0, "safe": 3.0, "verdict": 0.5}
    assert judge.average_scores([]) == {}


def test_judge_must_differ_from_the_generator(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    judge.get_settings.cache_clear()
    try:
        assert judge.pick_judge("anthropic", "claude-sonnet-5-5") == ("google", "gemini-flash-latest")
        with pytest.raises(SystemExit):
            judge.pick_judge("anthropic", "claude-sonnet-5-5", "anthropic", "claude-sonnet-5-5")
    finally:
        judge.get_settings.cache_clear()


def test_fill_dates():
    assert fill_dates({"a": ["{tomorrow}T13:00"]}, "2030-01-05") == {"a": ["2030-01-05T13:00"]}


def test_matchers():
    assert match(["vhop1"], {"contains": "VHOP1"})
    assert match(3_500_000_000, {"between": [3e9, 4e9]})
    assert not match(None, {"eq": 2})
    assert match("2030-01-05T07:00:00+00:00", {"time_is": "14:00"})
    windows = [{"start_at": "2030-01-05T12:30:00+07:00", "end_at": "2030-01-05T17:00:00+07:00"}]
    assert match(windows, {"window_covers": ["2030-01-05T13:00:00+07:00", "2030-01-05T17:00:00+07:00"]})
    assert not match(windows, {"window_covers": ["2030-01-05T12:00:00+07:00", "2030-01-05T17:00:00+07:00"]})


def _search(price: int, score: float) -> dict:
    return {"property": {"id": price, "price_vnd": price, "bedrooms": 2}, "match_score": score}


def test_evaluate_pass_and_fail():
    expect = {
        "tool_called": "search_properties",
        "args": {"bedrooms_min": {"eq": 2}},
        "results_all": {"price_vnd_max": 3_000_000_000},
        "results_sorted_by_score": True,
        "recommendations": "non_empty",
        "reply_not_matches": "0\\d{9}",
    }
    ok = Transcript(
        replies=["Có 2 căn phù hợp."],
        calls=[
            ToolCall(
                "search_properties",
                {"bedrooms_min": 2},
                {"ok": True, "data": {"results": [_search(2_900_000_000, 0.9), _search(2_800_000_000, 0.7)]}},
            )
        ],
        recommendations=2,
    )
    assert evaluate(expect, ok) == []

    bad = Transcript(
        replies=["Gọi chủ nhà số 0901234567 nhé"],
        calls=[
            ToolCall(
                "search_properties",
                {"bedrooms_min": 1},
                {"ok": True, "data": {"results": [_search(3_100_000_000, 0.5), _search(2_000_000_000, 0.8)]}},
            )
        ],
    )
    failures = evaluate(expect, bad)
    assert any("bedrooms_min" in f for f in failures)
    assert any("above" in f for f in failures)
    assert any("not ranked" in f for f in failures)
    assert any("expected recommendations" in f for f in failures)
    assert any("forbidden" in f for f in failures)


def test_evaluate_forbidden_tool_and_retry_with_better_args():
    t = Transcript(
        replies=["ok"],
        calls=[
            ToolCall("get_property_detail", {"property_id": 9}),
            ToolCall("get_property_detail", {"property_id": 10}),
            ToolCall("create_viewing_request", {"property_id": 10}),
        ],
    )
    failures = evaluate(
        {
            "tool_called": "get_property_detail",
            "args": {"property_id": {"eq": 10}},
            "tool_not_called": ["create_viewing_request"],
        },
        t,
    )
    assert failures == ["must not call create_viewing_request"]
