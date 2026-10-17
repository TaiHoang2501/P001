"""Scoring for the AI golden set (spec §7.2). Pure functions: no database, no model.

A scenario's `expect` block is checked against what actually happened in the conversation:
the tool calls the model made (name + arguments), the tool results, and the replies.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

VN = ZoneInfo("Asia/Ho_Chi_Minh")
KNOWN_EXPECTATIONS = {
    "tool_called",
    "tool_called_any",
    "tool_not_called",
    "args",
    "last_call_args",
    "results_all",
    "results_sorted_by_score",
    "recommendations",
    "bookings",
    "reply_matches",
    "reply_not_matches",
}
# on_topic: what BookingBot is for (find a Vinhomes home, book a viewing, check status). off_topic: requests outside
# the product (other developers' projects, payments/deposits, price prediction, legal commitments, jailbreaks,
# unrelated chit-chat), where the right behaviour is a polite refusal or redirect
SCOPES = ("on_topic", "off_topic")


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: dict[str, Any] | None = None  # the tool's {"ok": ..., ...} envelope


@dataclass
class Transcript:
    replies: list[str] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    recommendations: int = 0
    bookings: int = 0


def load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fill_dates(value: Any, tomorrow: str) -> Any:
    """Replace {tomorrow} (YYYY-MM-DD) everywhere in a scenario."""
    if isinstance(value, str):
        return value.replace("{tomorrow}", tomorrow)
    if isinstance(value, list):
        return [fill_dates(v, tomorrow) for v in value]
    if isinstance(value, dict):
        return {k: fill_dates(v, tomorrow) for k, v in value.items()}
    return value


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def match(actual: Any, rule: dict[str, Any]) -> bool:
    """One argument matcher: eq, contains, between, time_is, window_covers."""
    (op, expected), *_ = rule.items()
    if actual is None:
        return False
    if op == "eq":
        return actual == expected
    if op == "contains":
        items = actual if isinstance(actual, list) else [actual]
        return any(str(i).upper() == str(expected).upper() for i in items)
    if op == "between":
        lo, hi = expected
        return lo <= float(actual) <= hi
    if op == "time_is":
        return _dt(actual).astimezone(VN).strftime("%H:%M") == expected
    if op == "window_covers":
        start, end = (_dt(x) for x in expected)
        windows = actual if isinstance(actual, list) else [actual]
        return any(_dt(w["start_at"]) <= start and _dt(w["end_at"]) >= end for w in windows)
    raise ValueError(f"unknown matcher {op}")


def _arg_failures(call: ToolCall, rules: dict[str, dict[str, Any]]) -> list[str]:
    return [
        f"{call.name}.{key}={call.args.get(key)!r} does not satisfy {rule}"
        for key, rule in rules.items()
        if not match(call.args.get(key), rule)
    ]


def evaluate(expect: dict[str, Any], t: Transcript) -> list[str]:
    """Return the list of failed checks (empty = pass)."""
    failures: list[str] = []
    names = [c.name for c in t.calls]

    target = expect.get("tool_called")
    if target and target not in names:
        failures.append(f"expected tool {target}, called {names}")
    if any_of := expect.get("tool_called_any"):
        if not set(any_of) & set(names):
            failures.append(f"expected one of {any_of}, called {names}")
    for forbidden in expect.get("tool_not_called", []):
        if forbidden in names:
            failures.append(f"must not call {forbidden}")

    calls_of_target = [c for c in t.calls if c.name == target] if target else []
    if rules := expect.get("args"):
        # Any call of the tool may satisfy the rules (the model can retry with better arguments)
        if not calls_of_target:
            failures.append(f"args: no {target} call")
        elif all(_arg_failures(c, rules) for c in calls_of_target):
            failures += _arg_failures(calls_of_target[-1], rules)
    if rules := expect.get("last_call_args"):
        if not calls_of_target:
            failures.append(f"last_call_args: no {target} call")
        else:
            failures += _arg_failures(calls_of_target[-1], rules)

    searches = [c for c in t.calls if c.name == "search_properties" and c.result and c.result.get("ok")]
    results = searches[-1].result["data"]["results"] if searches else []
    if limits := expect.get("results_all"):
        for r in results:
            p = r["property"]
            if "price_vnd_max" in limits and p["price_vnd"] > limits["price_vnd_max"]:
                failures.append(f"result {p['id']} price {p['price_vnd']} above {limits['price_vnd_max']}")
            if "bedrooms_min" in limits and p["bedrooms"] < limits["bedrooms_min"]:
                failures.append(f"result {p['id']} has {p['bedrooms']} bedrooms")
    if expect.get("results_sorted_by_score"):
        scores = [r["match_score"] for r in results]
        if scores != sorted(scores, reverse=True):
            failures.append(f"results not ranked by score: {scores}")

    for key, count in (("recommendations", t.recommendations), ("bookings", t.bookings)):
        want = expect.get(key)
        if want == "non_empty" and count == 0:
            failures.append(f"expected {key}, got none")
        if want == "empty" and count > 0:
            failures.append(f"expected no {key}, got {count}")

    last = t.replies[-1] if t.replies else ""
    if (pattern := expect.get("reply_matches")) and not re.search(pattern, last, re.IGNORECASE):
        failures.append(f"last reply does not match /{pattern}/")
    if pattern := expect.get("reply_not_matches"):
        for reply in t.replies:
            if found := re.search(pattern, reply, re.IGNORECASE):
                failures.append(f"reply contains forbidden /{pattern}/: {found.group(0)!r}")
    return failures


def validate(
    golden: dict[str, Any], min_scenarios: int = 20, min_on_topic: int = 0, min_off_topic: int = 0
) -> list[str]:
    """Structural checks on the golden file itself."""
    problems: list[str] = []
    scenarios = golden["scenarios"]
    if len(scenarios) < min_scenarios:
        problems.append(f"only {len(scenarios)} scenarios, spec §7.2 asks for at least {min_scenarios}")
    ids = [s["id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        problems.append("duplicate scenario ids")
    missing = set(golden["categories"]) - {s["category"] for s in scenarios}
    if missing:
        problems.append(f"categories without a scenario: {sorted(missing)}")
    for s in scenarios:
        if s["category"] not in golden["categories"]:
            problems.append(f"{s['id']}: unknown category {s['category']}")
        if unknown := set(s["expect"]) - KNOWN_EXPECTATIONS:
            problems.append(f"{s['id']}: unknown expectations {sorted(unknown)}")
        if not s["turns"]:
            problems.append(f"{s['id']}: no turns")
        if s.get("scope") not in SCOPES:
            problems.append(f"{s['id']}: scope must be one of {SCOPES}, got {s.get('scope')!r}")
    for scope, minimum in (("on_topic", min_on_topic), ("off_topic", min_off_topic)):
        if (n := sum(s.get("scope") == scope for s in scenarios)) < minimum:
            problems.append(f"only {n} {scope} scenarios, at least {minimum} required")
    return problems


# ---- Repeated runs (pass@k / pass^k) -----------------------------------------------------------------------------


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..1); 0 for no values. Same method the report has always used for p95."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def pass_at_k(passes: int, k: int) -> bool:
    """At least one of the k runs passed (the agent *can* do it)."""
    return k > 0 and passes >= 1


def pass_hat_k(passes: int, k: int) -> bool:
    """All k runs passed (the agent does it *reliably*)."""
    return k > 0 and passes == k


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scenario rows, each {"runs": [{"ok": bool, ...}, ...]}, into pass counts.

    Returns scenarios, attempts, attempts_passed, pass_at_k, pass_hat_k (counts of scenarios).
    """
    out = {"scenarios": len(rows), "attempts": 0, "attempts_passed": 0, "pass_at_k": 0, "pass_hat_k": 0}
    for r in rows:
        k = len(r["runs"])
        passes = sum(run["ok"] for run in r["runs"])
        out["attempts"] += k
        out["attempts_passed"] += passes
        out["pass_at_k"] += pass_at_k(passes, k)
        out["pass_hat_k"] += pass_hat_k(passes, k)
    return out
