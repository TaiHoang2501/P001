"""In-process periodic jobs (MVP; move to a real scheduler/worker when running several API replicas).

- Expire viewing holds whose window has ended (spec §4.13 rule 4).
- Deliver T-24h / T-2h viewing reminders that are due (spec §4.19).
"""

import asyncio
import logging

from src.config import get_settings
from src.db.session import get_sessionmaker
from src.services import hold_service, notification_service

logger = logging.getLogger(__name__)


def run_once() -> None:
    with get_sessionmaker()() as db:
        expired = hold_service.expire_finished(db)
        if expired:
            logger.info("Expired %d viewing hold(s)", expired)
        reminders = notification_service.deliver_due(db)
        if reminders:
            logger.info("Delivered %d reminder(s)", reminders)


async def run_forever() -> None:
    interval = get_settings().job_interval_seconds
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:
            logger.exception("Periodic job failed")
        await asyncio.sleep(interval)
