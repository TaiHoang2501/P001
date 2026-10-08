"""Matching what the buyer asked for: "2 phòng ngủ" means 2, and a budget cap is not a target."""

from src.models.property import SearchCriteria
from src.services import agent_api


def _search(**criteria) -> list[dict]:
    result = agent_api.search_properties({"project_codes": ["VHOP1"], "limit": 20, **criteria})
    assert result["ok"] is True, result
    return result["data"]["results"]


def test_exact_bedrooms_returns_only_that_layout():
    recs = _search(bedrooms=2, budget_max=5_000_000_000)
    assert len(recs) >= 5  # the demo listings give Ocean Park 1 enough two-bedroom homes
    assert {r["property"]["bedrooms"] for r in recs} == {2}
    # Shown as a matched criterion ("2 PN" in the buyer's needs)
    assert all(any(m["criterion"] == "bedrooms" for m in r["matched"]) for r in recs)


def test_at_least_bedrooms_ranks_the_exact_count_first():
    recs = _search(bedrooms_min=2, budget_max=6_000_000_000)
    beds = [r["property"]["bedrooms"] for r in recs]
    assert 3 in beds and 2 in beds
    first_three = beds.index(3)
    assert all(b == 2 for b in beds[:first_three])


def test_cheaper_home_within_budget_is_not_ranked_lower():
    # "dưới 5 tỷ": every home is within budget, so price does not push the pricier ones up
    recs = _search(bedrooms=2, budget_max=5_000_000_000)
    prices = [r["property"]["price_vnd"] for r in recs]
    assert prices == sorted(prices)
    assert len({r["match_score"] for r in recs}) == 1


def test_preferred_bedrooms_defaults_to_what_was_asked():
    assert SearchCriteria(bedrooms=2).preferred_bedrooms == 2
    assert SearchCriteria(bedrooms_min=3).preferred_bedrooms == 3
    assert SearchCriteria(bedrooms=2, preferred_bedrooms=1).preferred_bedrooms == 1
