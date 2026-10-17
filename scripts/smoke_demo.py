"""Smoke test of a deployed API: a demo buyer can sign in and use an authenticated endpoint.

    python scripts/smoke_demo.py https://bookingbot-api-xxxx.a.run.app
    python scripts/smoke_demo.py http://localhost:8000 --phone 0912345678 --role OWNER

Steps: GET /health -> POST /api/v1/auth/otp/request -> POST /api/v1/auth/otp/verify with the demo code
(DEMO_PHONES never get an SMS, their code is always 123456) -> GET /api/v1/auth/me with the token.
Exits 1 (with the failing step) if any step fails, so CI can run it right after a deploy.
Standard library only: runs on a bare CI runner without installing the project.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEMO_BUYER = "0901111222"
DEMO_CODE = "123456"


class SmokeError(Exception):
    pass


def _call(method: str, url: str, body: dict[str, Any] | None = None, token: str | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        return status, raw.decode(errors="replace")[:500]


def _expect(step: str, status: int, payload: Any, *ok: int) -> Any:
    if status not in ok:
        raise SmokeError(f"{step}: HTTP {status} {payload}")
    print(f"ok  {step} (HTTP {status})")
    return payload


def _wait_healthy(base: str, attempts: int, delay: float) -> None:
    last: str = ""
    for i in range(attempts):
        try:
            status, payload = _call("GET", f"{base}/health")
            if status == 200:
                print("ok  GET /health")
                return
            last = f"HTTP {status} {payload}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last = str(err)
        if i < attempts - 1:
            time.sleep(delay)
    raise SmokeError(f"GET /health: {last}")


def run(base: str, phone: str, role: str, code: str, attempts: int = 6, delay: float = 5.0) -> None:
    base = base.rstrip("/")
    api = f"{base}/api/v1"
    _wait_healthy(base, attempts, delay)

    sent = _expect(
        "POST /auth/otp/request",
        *_call("POST", f"{api}/auth/otp/request", {"target": phone, "role": role}),
        202,
    )
    if not isinstance(sent, dict) or not sent.get("demo"):
        raise SmokeError(f"POST /auth/otp/request: {phone} is not treated as a demo phone (DEMO_PHONES): {sent}")

    signed_in = _expect(
        "POST /auth/otp/verify",
        *_call("POST", f"{api}/auth/otp/verify", {"target": phone, "code": code}),
        200,
    )
    token = signed_in.get("access_token") if isinstance(signed_in, dict) else None
    if not token:
        raise SmokeError(f"POST /auth/otp/verify: no access_token in {signed_in}")

    me = _expect("GET /auth/me", *_call("GET", f"{api}/auth/me", token=token), 200)
    if not isinstance(me, dict) or me.get("role") != role or me.get("phone") != phone:
        raise SmokeError(f"GET /auth/me: expected the {role} account of {phone}, got {me}")
    print(f"ok  signed in as user #{me.get('id')} ({role})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url", help="API base URL, e.g. https://bookingbot-api-xxxx.a.run.app")
    parser.add_argument("--phone", default=DEMO_BUYER, help=f"demo phone (default {DEMO_BUYER}, a demo buyer)")
    parser.add_argument("--role", default="CUSTOMER", choices=["CUSTOMER", "OWNER"], help="account kind of the phone")
    parser.add_argument("--code", default=DEMO_CODE, help="OTP of the demo phones (default 123456)")
    parser.add_argument("--attempts", type=int, default=6, help="tries of /health while the service starts")
    args = parser.parse_args()
    try:
        run(args.base_url, args.phone, args.role, args.code, attempts=args.attempts)
    except (SmokeError, urllib.error.URLError, TimeoutError, ConnectionError) as err:
        print(f"FAIL {err}", file=sys.stderr)
        return 1
    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
