"""Pure scheduling math (spec §4.8, §9.5): no database, no clock, easy to test.

Buyer availability ∩ Seller availability − busy periods → candidate viewing start times.
All datetimes must be timezone-aware.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, order=True)
class Window:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Window bounds must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("Window end must be after start")


def merge(windows: Iterable[Window]) -> list[Window]:
    """Sort and merge overlapping or touching windows."""
    merged: list[Window] = []
    for w in sorted(windows):
        if merged and w.start <= merged[-1].end:
            merged[-1] = Window(merged[-1].start, max(merged[-1].end, w.end))
        else:
            merged.append(w)
    return merged


def intersect(a: Iterable[Window], b: Iterable[Window]) -> list[Window]:
    """Time ranges present in both lists (AC-06: 14h–17h ∩ 14h30–16h = 14h30–16h)."""
    left, right = merge(a), merge(b)
    out: list[Window] = []
    i = j = 0
    while i < len(left) and j < len(right):
        start = max(left[i].start, right[j].start)
        end = min(left[i].end, right[j].end)
        if start < end:
            out.append(Window(start, end))
        if left[i].end < right[j].end:
            i += 1
        else:
            j += 1
    return out


def subtract(windows: Iterable[Window], busy: Iterable[Window]) -> list[Window]:
    """Remove busy periods (existing bookings/holds) from the windows."""
    free = merge(windows)
    for b in merge(busy):
        next_free: list[Window] = []
        for w in free:
            if b.end <= w.start or b.start >= w.end:
                next_free.append(w)
                continue
            if w.start < b.start:
                next_free.append(Window(w.start, b.start))
            if b.end < w.end:
                next_free.append(Window(b.end, w.end))
        free = next_free
    return free


def _ceil_to_step(t: datetime, step: timedelta) -> datetime:
    # Grid is aligned to the epoch, so a 30-min step lands on :00/:30 in whole-hour offsets like UTC+7
    offset = (t - _EPOCH) % step
    return t if offset == timedelta(0) else t + (step - offset)


def candidate_starts(
    windows: Iterable[Window],
    *,
    duration: timedelta,
    step: timedelta,
    not_before: datetime,
    limit: int | None = None,
) -> list[datetime]:
    """Start times on the step grid where a viewing of `duration` fits inside a window."""
    starts: list[datetime] = []
    for w in merge(windows):
        t = _ceil_to_step(max(w.start, not_before), step)
        while t + duration <= w.end:
            starts.append(t)
            if limit is not None and len(starts) >= limit:
                return starts
            t += step
    return starts
