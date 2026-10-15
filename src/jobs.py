"""In-process periodic jobs (MVP; move to a real scheduler/worker when running several API replicas).

- Expire viewing holds whose window has ended (spec §4.13 rule 4).
- Deliver T-24h / T-2h viewing reminders that are due (spec §4.19).
- Escalate viewing requests the seller has not answered in time (spec §4.8 HITL); close those whose viewing
  time has come (EXPIRED) and new times asked for that passed unanswered.
- Agent follow-ups: alternatives for requests left unanswered or rejected; reminders worded for the buyer.
- After a viewing: remind the owner once to record it; close it as UNREPORTED if nobody did in time.
- Drop developer traces of chat turns older than AI_TRACE_RETENTION_DAYS.
- Demo only (SEED_DEMO_DATA): once a day, keep the demo owners' viewing slots 14 days ahead — an instance kept
  warm can run for days without the start-up seed.
"""

import asyncio
import logging
from datetime import date

from sqlalchemy.orm import Session

from src.config import get_settings
from src.db import seed
from src.db.session import get_sessionmaker
from src.services import (
    agent_followup,
    ai_trace,
    booking_service,
    escalation_service,
    hold_service,
    notification_service,
    viewing_outcome_service,
)

logger = logging.getLogger(__name__)

DEMO_SLOT_DAYS = 14
_demo_slots_topped_up_on: date | None = None


def run_once() -> None:
    with get_sessionmaker()() as db:
        expired = hold_service.expire_finished(db)
        if expired:
            logger.info("Expired %d viewing hold(s)", expired)
        agent_followup.personalize_due_reminders(db)
        reminders = notification_service.deliver_due(db)
        if reminders:
            logger.info("Delivered %d reminder(s)", reminders)
        # Requests whose time has come close first, so none of them is sent to the queue on its way out
        expired = booking_service.expire_unanswered(db)
        if expired:
            logger.info("Closed %d viewing request(s) past their time", expired)
        escalated = escalation_service.escalate_unanswered_requests(db)
        if escalated:
            logger.info("Escalated %d unanswered viewing request(s)", escalated)
        settled = escalation_service.settle_stale_cases(db)
        if settled:
            logger.info("Closed %d case(s) whose request was dealt with", settled)
        escalation_service.retire_closed_case_notices(db)
        db.commit()
        reminded, unreported = viewing_outcome_service.remind_and_close(db)
        if reminded or unreported:
            logger.info("Viewing outcomes: %d owner reminder(s), %d closed unreported", reminded, unreported)
        followed_up = agent_followup.run(db)
        if followed_up:
            logger.info("Agent followed up %d viewing request(s)", followed_up)
        purged = ai_trace.purge_old(db)
        if purged:
            logger.info("Dropped %d old chat trace(s)", purged)
        _top_up_demo_slots(db)


def _top_up_demo_slots(db: Session) -> None:
    global _demo_slots_topped_up_on
    if not get_settings().seed_demo_data or _demo_slots_topped_up_on == date.today():
        return
    added = seed.ensure_slots(db, DEMO_SLOT_DAYS)
    _demo_slots_topped_up_on = date.today()
    if added:
        logger.info("Added %d demo viewing slot(s)", added)


async def run_forever() -> None:
    interval = get_settings().job_interval_seconds
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:
            logger.exception("Periodic job failed")
        await asyncio.sleep(interval)
