"""Escalations: the operator's exception queue, and a requester's view of their own cases."""

from fastapi import APIRouter

from src.core.deps import AnyActor, DbSession, OperatorActor
from src.db.models import EscalationStatus
from src.models.booking import BookingOut, ViewingOutcome
from src.models.escalation import EscalationOut, ResolveRequest
from src.models.ownership import OperatorNote, OwnershipCaseOut, UnlockRequest
from src.services import escalation_service, ownership_support_service, viewing_outcome_service

router = APIRouter(tags=["escalations"])


@router.get("/escalations", response_model=list[EscalationOut])
def my_escalations(actor: AnyActor, db: DbSession) -> list[EscalationOut]:
    """Cases raised on my behalf (e.g. by the AI assistant) and their outcome."""
    return escalation_service.list_mine(db, actor)


@router.get("/operator/escalations", response_model=list[EscalationOut])
def queue(actor: OperatorActor, db: DbSession, status: EscalationStatus | None = None) -> list[EscalationOut]:
    return escalation_service.list_queue(db, status)


@router.post("/operator/escalations/{escalation_id}/assign", response_model=EscalationOut)
def assign(escalation_id: int, actor: OperatorActor, db: DbSession) -> EscalationOut:
    return escalation_service.assign(db, actor, escalation_id)


@router.post("/operator/escalations/{escalation_id}/resolve", response_model=EscalationOut)
def resolve(escalation_id: int, data: ResolveRequest, actor: OperatorActor, db: DbSession) -> EscalationOut:
    return escalation_service.close(db, actor, escalation_id, data.resolution)


@router.post("/operator/escalations/{escalation_id}/dismiss", response_model=EscalationOut)
def dismiss(escalation_id: int, data: ResolveRequest, actor: OperatorActor, db: DbSession) -> EscalationOut:
    return escalation_service.close(db, actor, escalation_id, data.resolution, dismissed=True)


# ---------- Ownership support cases (red book verification the seller could not finish alone) ----------


@router.get("/operator/escalations/{escalation_id}/ownership", response_model=OwnershipCaseOut)
def ownership_case(escalation_id: int, actor: OperatorActor, db: DbSession) -> OwnershipCaseOut:
    return ownership_support_service.case(db, escalation_id)


@router.post("/operator/escalations/{escalation_id}/ownership/unlock", response_model=OwnershipCaseOut)
def unlock_red_book(escalation_id: int, data: UnlockRequest, actor: OperatorActor, db: DbSession) -> OwnershipCaseOut:
    """Unlock the red book (and set the owner's new phone); the seller then verifies with the OTP again."""
    return ownership_support_service.unlock(db, actor, escalation_id, data.owner_phone)


@router.post("/operator/escalations/{escalation_id}/ownership/verify", response_model=OwnershipCaseOut)
def verify_red_book(escalation_id: int, data: OperatorNote, actor: OperatorActor, db: DbSession) -> OwnershipCaseOut:
    """Verify by hand after checking the documents."""
    return ownership_support_service.verify(db, actor, escalation_id, data.note)


@router.post("/operator/escalations/{escalation_id}/ownership/revoke", response_model=OwnershipCaseOut)
def revoke_red_book(escalation_id: int, data: OperatorNote, actor: OperatorActor, db: DbSession) -> OwnershipCaseOut:
    """Take back a wrong verification; its listing comes off the market and its viewings are cancelled."""
    return ownership_support_service.revoke(db, actor, escalation_id, data.note)


@router.post("/operator/escalations/{escalation_id}/viewing-outcome", response_model=BookingOut)
def record_viewing_outcome(escalation_id: int, data: ViewingOutcome, actor: OperatorActor, db: DbSession) -> BookingOut:
    """A viewing dispute: what really happened, after calling both sides. Closes the case and tells both."""
    return viewing_outcome_service.record_outcome(db, actor, escalation_id, data.outcome, data.note.strip())
