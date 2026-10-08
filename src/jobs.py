"""In-process periodic jobs (MVP; move to a real scheduler/worker when running several API replicas).

- Expire viewing holds whose window has ended (spec §4.13 rule 4).
- Deliver T-24h / T-2h viewing reminders that are due (spec §4.19).
- Escalate viewing requests the seller has not answered in time (spec §4.8 HITL).
- Agent follow-ups: alternatives for requests left unanswered or rejected; reminders worded for the buyer.
- After a viewing: remind the owner once to record it; close it as UNREPORTED if nobody did in time.
"""

import asyncio
import logging

from src.config import get_settings
from src.db.session import get_sessionmaker
from src.services import agent_followup, escalation_service, hold_service, notification_service, viewing_outcome_service

logger = logging.getLogger(__name__)


def run_once() -> None:
    with get_sessionmaker()() as db:
        expired = hold_service.expire_finished(db)
        if expired:
            logger.info("Expired %d viewing hold(s)", expired)
        agent_followup.personalize_due_reminders(db)
        reminders = notification_service.deliver_due(db)
        if reminders:
            logger.info("Delivered %d reminder(s)", reminders)
        escalated = escalation_service.escalate_unanswered_requests(db)
        if escalated:
            logger.info("Escalated %d unanswered viewing request(s)", escalated)
        reminded, unreported = viewing_outcome_service.remind_and_close(db)
        if reminded or unreported:
            logger.info("Viewing outcomes: %d owner reminder(s), %d closed unreported", reminded, unreported)
        followed_up = agent_followup.run(db)
        if followed_up:
            logger.info("Agent followed up %d viewing request(s)", followed_up)


async def run_forever() -> None:
    interval = get_settings().job_interval_seconds
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:
            logger.exception("Periodic job failed")
        await asyncio.sleep(interval)
