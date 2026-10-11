"""Developer view of the AI chat traces (table ai_turns). Not for operators: this is for debugging the assistant.

Usage:
    python scripts/ai_traces.py recent [-n 20] [--errors] [--guests]   # latest turns, one line each
    python scripts/ai_traces.py show <trace_id>                        # one turn: steps, messages, tool calls
    python scripts/ai_traces.py stats [--days 7]                       # error rate, latency, tokens, tools

A trace id is printed in the server log next to every failed turn and returned with each chat reply
(`trace_id` in the response / the `error` stream event).
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from src.db.models import AiMessage, AiTurn, MessageRole  # noqa: E402
from src.db.session import get_sessionmaker  # noqa: E402


def _who(t: AiTurn) -> str:
    return "guest" if t.guest else f"user {t.buyer_id}"


def _short(text: str | None, n: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def recent(n: int, errors: bool, guests: bool) -> None:
    with get_sessionmaker()() as db:
        q = select(AiTurn).order_by(AiTurn.id.desc()).limit(n)
        if errors:
            q = q.where(AiTurn.status == "ERROR")
        if guests:
            q = q.where(AiTurn.guest.is_(True))
        for t in db.scalars(q):
            tokens = (t.prompt_tokens or 0) + (t.completion_tokens or 0)
            print(
                f"{t.created_at:%Y-%m-%d %H:%M:%S}  {t.trace_id}  {t.status:<5} {_who(t):<10} "
                f"{t.latency_ms / 1000:5.1f}s  llm {t.llm_calls} tool {t.tool_calls}  {tokens:>6} tok  "
                f"{_short(t.error_type or t.message)}"
            )


def show(trace_id: str) -> None:
    with get_sessionmaker()() as db:
        t = db.scalar(select(AiTurn).where(AiTurn.trace_id == trace_id))
        if t is None:
            sys.exit(f"No trace {trace_id}")
        print(f"trace     {t.trace_id}   {t.created_at:%Y-%m-%d %H:%M:%S %Z}")
        print(f"who       {_who(t)}   conversation {t.conversation_id}   {'stream' if t.streamed else 'plain'}")
        print(f"status    {t.status}" + (f"   {t.error_type}: {t.error_message}" if t.error_type else ""))
        print(f"model     {t.model}   llm calls {t.llm_calls}   tool calls {t.tool_calls}")
        print(f"tokens    in {t.prompt_tokens}   out {t.completion_tokens}   latency {t.latency_ms} ms")
        print(f"message   {t.message}")
        print("\nsteps")
        for s in t.steps:
            extra = ""
            if s["kind"] == "llm":
                extra = f"tokens {s.get('prompt_tokens')}/{s.get('completion_tokens')}"
                if s.get("tool_calls"):
                    extra += f"  -> {', '.join(s['tool_calls'])}"
            if s.get("error"):
                extra += f"  ERROR {s['error']}"
            ok = "ok " if s.get("ok") else ("ERR" if s.get("ok") is False else "…  ")
            print(f"  +{s['at_ms']:>6} ms  {s['kind']:<4} {ok} {str(s.get('ms')):>6} ms  {s.get('name')}  {extra}")
        print("\nmessages")
        for m in db.scalars(select(AiMessage).where(AiMessage.turn_id == t.id).order_by(AiMessage.id)):
            if m.role == MessageRole.TOOL:
                result = json.dumps(m.tool_result, ensure_ascii=False)
                print(f"  TOOL {m.tool_name} ok={m.tool_ok} args={json.dumps(m.tool_args, ensure_ascii=False)}")
                print(f"       -> {_short(result, 300)}")
            else:
                calls = f"  [calls {', '.join(c['name'] for c in m.tool_calls)}]" if m.tool_calls else ""
                print(f"  {m.role.value:<9} {_short(m.content, 300)}{calls}")


def stats(days: int) -> None:
    since = datetime.now(UTC) - timedelta(days=days)
    with get_sessionmaker()() as db:
        turns = db.scalars(select(AiTurn).where(AiTurn.created_at >= since)).all()
    if not turns:
        print(f"No turns in the last {days} day(s).")
        return
    latencies = sorted(t.latency_ms for t in turns if t.status == "OK")

    def pct(p: float) -> str:
        return f"{latencies[min(len(latencies) - 1, int(p * len(latencies)))] / 1000:.1f}s" if latencies else "-"

    errors = [t for t in turns if t.status == "ERROR"]
    tools: dict[str, list[bool]] = {}
    for t in turns:
        for s in t.steps:
            if s["kind"] == "tool":
                tools.setdefault(s.get("name") or "?", []).append(bool(s.get("ok")))
    print(f"Last {days} day(s): {len(turns)} turns ({sum(t.guest for t in turns)} by guests)")
    print(f"  failed      {len(errors)} ({len(errors) / len(turns):.1%})")
    print(f"  latency     p50 {pct(0.5)}   p95 {pct(0.95)}")
    print(
        f"  tokens      in {sum(t.prompt_tokens or 0 for t in turns)}   out {sum(t.completion_tokens or 0 for t in turns)}"
    )
    print("  tools       calls / failed")
    for name, results in sorted(tools.items(), key=lambda kv: -len(kv[1])):
        print(f"    {name:<28} {len(results):>5} / {results.count(False)}")
    if errors:
        kinds: dict[str, int] = {}
        for t in errors:
            kinds[t.error_type or "?"] = kinds.get(t.error_type or "?", 0) + 1
        print("  errors      " + ", ".join(f"{k} x{v}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])))


def main() -> None:
    parser = argparse.ArgumentParser(description="Developer view of AI chat traces")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("recent", help="latest turns")
    p.add_argument("-n", type=int, default=20)
    p.add_argument("--errors", action="store_true", help="failed turns only")
    p.add_argument("--guests", action="store_true", help="guests' turns only")
    p = sub.add_parser("show", help="one turn in detail")
    p.add_argument("trace_id")
    p = sub.add_parser("stats", help="summary")
    p.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    if args.cmd == "recent":
        recent(args.n, args.errors, args.guests)
    elif args.cmd == "show":
        show(args.trace_id)
    else:
        stats(args.days)


if __name__ == "__main__":
    main()
