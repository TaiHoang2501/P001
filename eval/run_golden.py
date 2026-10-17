"""Run the AI golden set (eval/golden_set.json) against the real agent and model.

Usage (from the repo root, with LLM_PROVIDER + key in .env):
    python eval/run_golden.py                 # all scenarios
    python eval/run_golden.py EXT-01 SCHED-01 # a subset
    python eval/run_golden.py --sleep 5       # pause before each turn (Gemini free tier: 15 requests/min)
    python eval/run_golden.py --runs 3        # each scenario 3 times: pass@3 (>=1 passed) and pass^3 (all passed)
    python eval/run_golden.py --runs 3 --judge                       # + LLM judge on another provider/model
    python eval/run_golden.py --judge --judge-provider openrouter --judge-model openai/gpt-4o-mini

Uses a separate database (<DATABASE_URL db>_eval, or GOLDEN_DATABASE_URL), re-seeded before every run of
every scenario so runs cannot affect each other. Writes eval/results/golden_report.md and the raw per-run
data (replies, tool calls, judge scores) to eval/results/golden_runs.json.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from src.config import Settings, get_settings  # noqa: E402


def _eval_db_url() -> str:
    if url := os.environ.get("GOLDEN_DATABASE_URL"):
        return url
    url = make_url(Settings().database_url)
    return url.set(database=f"{url.database}_eval").render_as_string(hide_password=False)


# Point the whole app at the eval database before anything opens a connection
EVAL_DB = _eval_db_url()
os.environ["DATABASE_URL"] = EVAL_DB
os.environ.setdefault("APP_ENV", "development")
get_settings.cache_clear()

from alembic.config import Config  # noqa: E402
from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

from alembic import command  # noqa: E402
from src.agents import graph as agent_graph  # noqa: E402
from src.core.actor import Actor  # noqa: E402
from src.db.models import User  # noqa: E402
from src.db.seed import seed  # noqa: E402
from src.db.session import get_sessionmaker  # noqa: E402
from src.evaluation import judge as llm_judge  # noqa: E402
from src.evaluation.golden import (  # noqa: E402
    ToolCall,
    Transcript,
    evaluate,
    fill_dates,
    load,
    percentile,
    summarize,
    validate,
)
from src.models.schemas import ChatRequest  # noqa: E402
from src.services import chat_service  # noqa: E402

BUYER_ID = 1  # seeded buyer "Nguyễn Văn An"
VN = ZoneInfo("Asia/Ho_Chi_Minh")


def prepare_database() -> None:
    url = make_url(EVAL_DB)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}):
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", EVAL_DB.replace("%", "%%"))
    command.upgrade(cfg, "head")


def reseed() -> None:
    with get_sessionmaker()() as db:
        seed(db, reset=True)


async def run_scenario(scenario: dict, sleep: float, run: int = 1) -> tuple[Transcript, list[float]]:
    reseed()
    with get_sessionmaker()() as db:
        actor = Actor(user=db.get(User, BUYER_ID))
        db.expunge(actor.user)
    conv_id = f"{scenario['id']}-r{run}-{int(time.time())}"
    transcript = Transcript()
    latencies: list[float] = []
    for message in scenario["turns"]:
        if sleep:  # also between scenarios: free-tier quotas count requests per minute
            await asyncio.sleep(sleep)
        started = time.perf_counter()
        res = await chat_service.chat(actor, ChatRequest(message=message, conversation_id=conv_id))
        latencies.append(time.perf_counter() - started)
        transcript.replies.append(res.reply)
        transcript.recommendations += len(res.recommendations)
        transcript.bookings += len(res.bookings)

    # Tool calls and their results, in order, from the conversation state
    state = await agent_graph.get_agent().aget_state({"configurable": {"thread_id": f"{BUYER_ID}:{conv_id}"}})
    pending: dict[str, ToolCall] = {}
    for m in state.values.get("messages", []):
        if isinstance(m, AIMessage):
            for c in m.tool_calls:
                call = ToolCall(name=c["name"], args=c["args"])
                pending[c["id"]] = call
                transcript.calls.append(call)
        elif isinstance(m, ToolMessage) and m.tool_call_id in pending:
            pending[m.tool_call_id].result = m.artifact if isinstance(m.artifact, dict) else None
    return transcript, latencies


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / max(d, 1):.0%})"


def _judge_cells(scores: list[dict]) -> str:
    avg = llm_judge.average_scores(scores)
    if not avg:
        return " – | – | – | – | – |"
    return " " + " | ".join(f"{avg[c]:.2f}" for c in llm_judge.CRITERIA) + f" | {avg['verdict']:.0%} |"


def report(
    rows: list[dict], categories: list[str], latencies: list[float], path: Path, judge_model: str | None = None
) -> str:
    """Markdown report. With one run per scenario and no judge, the layout is the same as before --runs existed."""
    k = max((len(r["runs"]) for r in rows), default=1)
    total = summarize(rows)
    settings = get_settings()
    p50, p95 = percentile(latencies, 0.5), percentile(latencies, 0.95)
    lines = [
        "# AI golden set report",
        "",
        f"Run: {datetime.now(VN):%Y-%m-%d %H:%M} (UTC+7) · model `{settings.llm_provider}/{settings.llm_model}` · "
        f"{len(rows)} scenarios" + (f" × {k} runs" if k > 1 else ""),
        "",
    ]
    if k == 1:
        lines.append(
            f"**Pass rate: {_pct(total['attempts_passed'], total['attempts'])}** · "
            f"turn latency p50 {p50:.1f}s, p95 {p95:.1f}s (spec §2.2 target ≤ 5s)"
        )
    else:
        lines += [
            f"**pass@{k}: {_pct(total['pass_at_k'], total['scenarios'])}** (≥1 of {k} runs passed) · "
            f"**pass^{k}: {_pct(total['pass_hat_k'], total['scenarios'])}** (all {k} runs passed) · "
            f"pass rate per run: {_pct(total['attempts_passed'], total['attempts'])}",
            "",
            f"Turn latency ({len(latencies)} turns): p50 {p50:.1f}s, p95 {p95:.1f}s (spec §2.2 target ≤ 5s)",
        ]
    if judge_model:
        lines += [
            "",
            f"LLM judge: `{judge_model}` (a different model from the generator). Scores 1–5 per criterion, "
            "mean over judged runs; Judge OK = share of final replies the judge accepts.",
        ]

    def group_table(title: str, groups: list[tuple[str, list[dict]]]) -> None:
        if k == 1:
            head, sep = f"| {title} | Passed |", "|---|---|"
        else:
            head = f"| {title} | Scenarios | Runs passed | pass@{k} | pass^{k} |"
            sep = "|---|---|---|---|---|"
        if judge_model:
            head += " Grounded | Answers | Tone | Safe | Judge OK |"
            sep += "---|---|---|---|---|"
        lines.extend(["", head, sep])
        for name, in_group in groups:
            if not in_group:
                continue
            g = summarize(in_group)
            if k == 1:
                row = f"| {name} | {g['attempts_passed']}/{g['attempts']} |"
            else:
                row = (
                    f"| {name} | {g['scenarios']} | {_pct(g['attempts_passed'], g['attempts'])} | "
                    f"{_pct(g['pass_at_k'], g['scenarios'])} | {_pct(g['pass_hat_k'], g['scenarios'])} |"
                )
            if judge_model:
                row += _judge_cells([run["judge"] for r in in_group for run in r["runs"] if run.get("judge")])
            lines.append(row)

    group_table("Category", [(c, [r for r in rows if r["category"] == c]) for c in categories])
    scopes = [(s, [r for r in rows if r["scope"] == s]) for s in ("on_topic", "off_topic")]
    group_table("Scope", [*scopes, ("all", rows)])

    if k == 1:
        lines += ["", "| ID | Category | Result | Tools called | Notes |", "|---|---|---|---|---|"]
    else:
        lines += [
            "",
            "| ID | Category | Scope | Runs passed | Tools called (run 1) | Notes |",
            "|---|---|---|---|---|---|",
        ]
    for r in rows:
        failures = [f"run {i}: {f}" if k > 1 else f for i, run in enumerate(r["runs"], 1) for f in run["failures"]]
        judged = [run["judge"] for run in r["runs"] if run.get("judge")]
        if judged:
            worst = min(judged, key=lambda j: (j["verdict"], min(j[c] for c in llm_judge.CRITERIA)))
            if not worst["verdict"] or min(worst[c] for c in llm_judge.CRITERIA) < 4:
                failures.append(f"judge: {worst['reason']}")
        failures += [f"judge error: {run['judge_error']}" for run in r["runs"] if run.get("judge_error")]
        notes = "; ".join(failures).replace("|", "\\|").replace("\n", " ")[:300]
        tools = ", ".join(r["runs"][0]["tools"]) if r["runs"] else ""
        passes = sum(run["ok"] for run in r["runs"])
        if k == 1:
            lines.append(f"| {r['id']} | {r['category']} | {'PASS' if passes else 'FAIL'} | {tools} | {notes} |")
        else:
            lines.append(
                f"| {r['id']} | {r['category']} | {r['scope']} | {passes}/{len(r['runs'])} | {tools} | {notes} |"
            )
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return content


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="Scenario ids to run (default: all)")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds between turns")
    parser.add_argument("--runs", type=int, default=1, help="Runs per scenario (k for pass@k / pass^k)")
    parser.add_argument("--judge", action="store_true", help="Grade each final reply with an LLM judge")
    parser.add_argument(
        "--judge-provider",
        default=os.environ.get("EVAL_JUDGE_PROVIDER", ""),
        help="Judge provider (default: the first of openrouter/google/openai/anthropic with a key, not the generator's)",
    )
    parser.add_argument("--judge-model", default=os.environ.get("EVAL_JUDGE_MODEL", ""), help="Judge model")
    parser.add_argument(
        "--max-errors", type=int, default=5, help="Stop after this many provider errors in a row (rate limit, outage)"
    )
    parser.add_argument("--verbose", action="store_true", help="Print replies and tool calls")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    golden = load(ROOT / "eval" / "golden_set.json")
    if problems := validate(golden):
        print("Golden set is invalid:", *problems, sep="\n  ")
        return 2
    tomorrow = (datetime.now(UTC).astimezone(VN) + timedelta(days=1)).date().isoformat()
    scenarios = [fill_dates(s, tomorrow) for s in golden["scenarios"] if not args.ids or s["id"] in args.ids]

    settings = get_settings()
    judge_llm, judge_name = None, None
    if args.judge:
        provider, model = llm_judge.pick_judge(
            settings.llm_provider, settings.llm_model, args.judge_provider, args.judge_model
        )
        judge_llm, judge_name = llm_judge.make_judge_llm(provider, model), f"{provider}/{model}"
        print(f"Generator {settings.llm_provider}/{settings.llm_model} · judge {judge_name}")

    prepare_database()
    rows: list[dict] = []
    latencies: list[float] = []
    errors_in_row, aborted = 0, ""
    for s in scenarios:
        if aborted:
            break
        row: dict = {"id": s["id"], "category": s["category"], "scope": s["scope"], "runs": []}
        for run in range(1, args.runs + 1):
            transcript, lat = None, []
            try:
                transcript, lat = await run_scenario(s, args.sleep, run)
                failures = evaluate(s["expect"], transcript)
                tools = [c.name for c in transcript.calls]
                latencies += lat
                errors_in_row = 0
            except Exception as e:  # model/provider errors count as failures, the run continues
                failures, tools = [f"error: {type(e).__name__}: {str(e)[:200]}"], []
                errors_in_row += 1
            result: dict = {"run": run, "ok": not failures, "failures": failures, "tools": tools, "latencies": lat}
            if transcript is not None:
                result["replies"] = transcript.replies
                result["calls"] = [{"name": c.name, "args": c.args} for c in transcript.calls]
                if judge_llm is not None:
                    try:
                        score = await llm_judge.judge(judge_llm, s, transcript.replies, transcript.calls)
                        result["judge"] = score.model_dump()
                    except Exception as e:  # a failed grade is reported, not retried
                        result["judge_error"] = f"{type(e).__name__}: {str(e)[:200]}"
            row["runs"].append(result)
            tag = f"{s['id']}#{run}" if args.runs > 1 else s["id"]
            j = result.get("judge")
            jtxt = (
                f"  judge {'/'.join(str(j[c]) for c in llm_judge.CRITERIA)} {'OK' if j['verdict'] else 'NO'}"
                if j
                else ""
            )
            print(f"{tag:<11} {'PASS' if not failures else 'FAIL'}{jtxt}  {'; '.join(failures)[:160]}")
            if args.verbose and transcript is not None:
                for turn, reply in zip(s["turns"], transcript.replies, strict=False):
                    print(f"  > {turn}\n  < {reply[:400]}")
                print(f"  tools: {[(c.name, c.args) for c in transcript.calls]}")
            if errors_in_row >= args.max_errors:
                aborted = f"stopped after {errors_in_row} provider errors in a row (last: {failures[0]})"
                print(aborted)
                break
        rows.append(row)

    out = ROOT / "eval" / "results" / "golden_report.md"
    report(rows, golden["categories"], latencies, out, judge_name)
    if aborted:
        with out.open("a", encoding="utf-8") as f:
            f.write(f"\n**Run incomplete:** {aborted}.\n")
    raw = {
        "generated_at": datetime.now(VN).isoformat(timespec="seconds"),
        "generator": f"{settings.llm_provider}/{settings.llm_model}",
        "judge": judge_name,
        "runs_per_scenario": args.runs,
        "summary": summarize(rows),
        "latency_p50_s": round(percentile(latencies, 0.5), 2),
        "latency_p95_s": round(percentile(latencies, 0.95), 2),
        "aborted": aborted or None,
        "scenarios": rows,
    }
    raw_path = ROOT / "eval" / "results" / "golden_runs.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\nReport written to {out.relative_to(ROOT)} (raw runs: {raw_path.relative_to(ROOT)})")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
