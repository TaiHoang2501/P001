"""AI kill switch for developers: turn the buyer's AI assistant off or on, at once, on every server.

Usage:
    python scripts/ai_switch.py status
    python scripts/ai_switch.py off --reason "Gemini trả lời sai hàng loạt"
    python scripts/ai_switch.py on
    python scripts/ai_switch.py client-ip          # after a deploy: the IP guest rate limits see for you

Reads ADMIN_API_URL (e.g. https://bookingbot-api-xxxx.a.run.app, default http://localhost:8000) and
ADMIN_API_TOKEN from the environment or .env. While off, buyers see the maintenance notice with the support
hotline and no chat reaches the model; booking and owner confirmation keep working. Every change is audited.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    if value := os.environ.get(name):
        return value
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name and value.strip():
                return value.strip().strip('"').strip("'")
    return default


def _call(method: str, path: str, body: dict | None = None) -> dict:
    base = _env("ADMIN_API_URL", "http://localhost:8000").rstrip("/")
    token = _env("ADMIN_API_TOKEN")
    if not token:
        sys.exit("ADMIN_API_TOKEN is not set (environment or .env)")
    request = urllib.request.Request(
        f"{base}/api/v1/admin{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Admin-Token": token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach {base}: {e.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["status", "on", "off", "client-ip"])
    parser.add_argument("--reason", help="Why (kept in the audit log, shown to operators)")
    args = parser.parse_args()
    if args.command == "off" and not args.reason:
        parser.error('say why with --reason "..." (kept in the audit log)')
    if args.command == "client-ip":
        result = _call("GET", "/diagnostics/client-ip")
    elif args.command == "status":
        result = _call("GET", "/ai-assistant")
    else:
        result = _call("PUT", "/ai-assistant", {"enabled": args.command == "on", "reason": args.reason})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
