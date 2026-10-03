"""Run the API without --reload (local demo / background server).

On Windows uvicorn's default event loop (Proactor) cannot run psycopg's async driver, so the agent's
PostgreSQL memory would fall back to process memory; this picks the selector loop there instead.
(`uvicorn --reload` also uses the selector loop, but its reload cannot restart a server started without a
console window.)

    python scripts/run_api.py            # 0.0.0.0:8000, or $PORT
"""

import os
import sys

import uvicorn

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uvicorn.run(
        "src.main:app",
        host=os.environ.get("APP_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        loop="asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto",
    )
