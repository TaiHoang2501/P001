"""Send one chat turn to the live API and append the full exchange to runs.jsonl.

usage: python chat.py <case_id> <guest|buyer> <conversation_id> <message>
"""
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from datetime import timedelta, timezone

BASE = "https://bookingbot-api-vcmp.onrender.com/api/v1"
LOG = Path(__file__).with_name("runs.jsonl")


def post(path: str, body: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    case, mode, conv, msg = sys.argv[1:5]
    token = None
    if mode == "buyer":
        token = post("/auth/login", {"identifier": "0903333444", "password": "Password123!"})["access_token"]
    path = "/chat" if mode == "buyer" else "/chat/guest"
    t0 = time.perf_counter()
    resp = post(path, {"message": msg, "conversation_id": conv}, token)
    dt = time.perf_counter() - t0
    rec = {
        "case": case, "mode": mode, "endpoint": "POST /api/v1" + path, "conversation_id": conv,
        "at": datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds"),
        "latency_s": round(dt, 2), "message": msg, "response": resp,
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[{dt:.1f}s] REPLY:\n{resp['reply']}\n")
    for r in resp.get("recommendations", []):
        p = r["property"]
        print("REC", {k: p.get(k) for k in ("id", "code", "project_name", "bedrooms", "area_m2", "price", "status")}, "score", r["match_score"])
    print("viewing_times:", json.dumps(resp.get("viewing_times"), ensure_ascii=False)[:600])
    print("bookings:", json.dumps(resp.get("bookings"), ensure_ascii=False)[:800])
    print("needs_account:", resp.get("needs_account"), "pending:", resp.get("pending_viewing"))


main()
