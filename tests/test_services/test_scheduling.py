"""Scheduling math (spec §4.8, AC-06, AC-07)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.services.scheduling import Window, candidate_starts, intersect, merge, subtract

VN = ZoneInfo("Asia/Ho_Chi_Minh")
SAT = datetime(2030, 1, 5, tzinfo=VN)
HALF_HOUR = timedelta(minutes=30)


def at(hour: float) -> datetime:
    return SAT + timedelta(hours=hour)


def w(start: float, end: float) -> Window:
    return Window(at(start), at(end))


def test_ac06_buyer_and_seller_windows_intersect():
    # Buyer: Saturday 14h-17h, Seller: Saturday 14h30-16h
    assert intersect([w(14, 17)], [w(14.5, 16)]) == [w(14.5, 16)]


def test_ac06_spec_example_proposes_1430_1500_1530():
    common = intersect([w(14, 17)], [w(14.5, 16)])
    starts = candidate_starts(common, duration=HALF_HOUR, step=HALF_HOUR, not_before=at(0))
    assert starts == [at(14.5), at(15), at(15.5)]


def test_ac07_no_intersection():
    assert intersect([w(9, 11)], [w(14, 16)]) == []


def test_intersect_multiple_windows():
    buyer = [w(8, 10), w(13, 18)]
    seller = [w(9, 14), w(16, 17)]
    assert intersect(buyer, seller) == [w(9, 10), w(13, 14), w(16, 17)]


def test_touching_windows_do_not_intersect():
    assert intersect([w(9, 10)], [w(10, 11)]) == []


def test_merge_joins_overlapping_and_touching():
    assert merge([w(10, 11), w(9, 10), w(10.5, 12), w(14, 15)]) == [w(9, 12), w(14, 15)]


def test_subtract_busy_booking_splits_window():
    assert subtract([w(14, 17)], [w(15, 15.5)]) == [w(14, 15), w(15.5, 17)]


def test_subtract_busy_covering_whole_window():
    assert subtract([w(14, 15)], [w(13, 16)]) == []


def test_candidates_skip_busy_period():
    free = subtract([w(14, 16)], [w(14.5, 15)])
    starts = candidate_starts(free, duration=HALF_HOUR, step=HALF_HOUR, not_before=at(0))
    assert starts == [at(14), at(15), at(15.5)]


def test_candidates_start_on_grid_and_respect_not_before():
    starts = candidate_starts([w(14.25, 16)], duration=HALF_HOUR, step=HALF_HOUR, not_before=at(14.6))
    assert starts == [at(15), at(15.5)]


def test_candidates_need_room_for_full_viewing():
    starts = candidate_starts([w(14, 15)], duration=timedelta(minutes=45), step=HALF_HOUR, not_before=at(0))
    assert starts == [at(14)]


def test_candidates_limit():
    starts = candidate_starts([w(8, 20)], duration=HALF_HOUR, step=HALF_HOUR, not_before=at(0), limit=3)
    assert starts == [at(8), at(8.5), at(9)]


def test_window_rejects_naive_or_inverted_times():
    with pytest.raises(ValueError):
        Window(datetime(2030, 1, 5, 14), datetime(2030, 1, 5, 15))
    with pytest.raises(ValueError):
        w(15, 14)
