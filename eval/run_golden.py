"""Run the AI golden set (eval/golden_set.json) against the real agent and model.

Usage (from the repo root, with LLM_PROVIDER + key in .env):
    python eval/run_golden.py                 # all scenarios
    python eval/run_golden.py EXT-01 SCHED-01 # a subset
    python eval/run_golden.py --sleep 5       # pause before each turn (Gemini free tier: 15 requests/min)

Uses a separate database (<DATABASE_URL db>_eval, or GOLDEN_DATABASE_URL), re-seeded before every
scenario so scenarios cannot affect each other. Writes eval/results/golden_report.md.
"""

import argparse
import asyncio
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
from src.evaluation.golden import ToolCall, Transcript, evaluate, fill_dates, load, validate  # noqa: E402
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


async def run_scenario(scenario: dict, sleep: float) -> tuple[Transcript, list[float]]:
    reseed()
    with get_sessionmaker()() as db:
        actor = Actor(user=db.get(User, BUYER_ID))
        db.expunge(actor.user)
    conv_id = f"{scenario['id']}-{int(time.time())}"
    transcript = Transcript()
    latencies: list[float] = []
    for i, message in enumerate(scenario["turns"]):
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


def report(rows: list[dict], categories: list[str], latencies: list[float], path: Path) -> str:
    passed = sum(r["ok"] for r in rows)
    lat = sorted(latencies)
    p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else 0.0
    settings = get_settings()
    lines = [
        "# AI golden set report",
        "",
        f"Run: {datetime.now(VN):%Y-%m-%d %H:%M} (UTC+7) · model `{settings.llm_provider}/{settings.llm_model}` · "
        f"{len(rows)} scenarios",
        "",
        f"**Pass rate: {passed}/{len(rows)} ({passed / max(len(rows), 1):.0%})** · "
        f"turn latency p95 {p95:.1f}s (spec §2.2 target ≤ 5s)",
        "",
        "| Category | Passed |",
        "|---|---|",
    ]
    for cat in categories:
        in_cat = [r for r in rows if r["category"] == cat]
        if in_cat:
            lines.append(f"| {cat} | {sum(r['ok'] for r in in_cat)}/{len(in_cat)} |")
    lines += ["", "| ID | Category | Result | Tools called | Notes |", "|---|---|---|---|---|"]
    for r in rows:
        notes = "; ".join(r["failures"]).replace("|", "\\|")[:300]
        lines.append(
            f"| {r['id']} | {r['category']} | {'PASS' if r['ok'] else 'FAIL'} | {', '.join(r['tools'])} | {notes} |"
        )
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return content


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="Scenario ids to run (default: all)")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds between turns")
    parser.add_argument("--verbose", action="store_true", help="Print replies and tool calls")
    args = parser.parse_args()

    golden = load(ROOT / "eval" / "golden_set.json")
    if problems := validate(golden):
        print("Golden set is invalid:", *problems, sep="\n  ")
        return 2
    tomorrow = (datetime.now(UTC).astimezone(VN) + timedelta(days=1)).date().isoformat()
    scenarios = [fill_dates(s, tomorrow) for s in golden["scenarios"] if not args.ids or s["id"] in args.ids]

    prepare_database()
    rows, latencies = [], []
    for s in scenarios:
        transcript = None
        try:
            transcript, lat = await run_scenario(s, args.sleep)
            failures = evaluate(s["expect"], transcript)
            tools = [c.name for c in transcript.calls]
            latencies += lat
        except Exception as e:  # model/provider errors count as failures, the run continues
            failures, tools = [f"error: {type(e).__name__}: {e}"], []
        rows.append(
            {"id": s["id"], "category": s["category"], "ok": not failures, "failures": failures, "tools": tools}
        )
        print(f"{s['id']:<9} {'PASS' if not failures else 'FAIL'}  {'; '.join(failures)[:160]}")
        if args.verbose and transcript is not None:
            for turn, reply in zip(s["turns"], transcript.replies, strict=False):
                print(f"  > {turn}\n  < {reply[:400]}")
            print(f"  tools: {[(c.name, c.args) for c in transcript.calls]}")

    out = ROOT / "eval" / "results" / "golden_report.md"
    report(rows, golden["categories"], latencies, out)
    print(f"\nReport written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
