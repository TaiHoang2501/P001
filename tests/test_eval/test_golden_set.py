"""The golden set file is well-formed, and the scorer judges transcripts correctly (no LLM needed)."""

from pathlib import Path

from src.evaluation.golden import ToolCall, Transcript, evaluate, fill_dates, load, match, validate

GOLDEN = load(Path(__file__).resolve().parents[2] / "eval" / "golden_set.json")


def test_golden_set_covers_spec_7_2():
    assert validate(GOLDEN) == []
    assert len(GOLDEN["scenarios"]) >= 20
    assert len(GOLDEN["categories"]) == 14


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
