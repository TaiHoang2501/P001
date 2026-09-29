"""In-process periodic jobs (MVP; move to a real scheduler/worker when running several API replicas).

- Expire viewing holds whose window has ended (spec §4.13 rule 4).
"""

import asyncio
import logging

from src.config import get_settings
from src.db.session import get_sessionmaker
from src.services import hold_service

logger = logging.getLogger(__name__)


def run_once() -> None:
    with get_sessionmaker()() as db:
        expired = hold_service.expire_finished(db)
        if expired:
            logger.info("Expired %d viewing hold(s)", expired)


async def run_forever() -> None:
    interval = get_settings().job_interval_seconds
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:
            logger.exception("Periodic job failed")
        await asyncio.sleep(interval)
