"""Escalations: the operator's exception queue, and a requester's view of their own cases."""

from fastapi import APIRouter

from src.core.deps import AnyActor, DbSession, OperatorActor
from src.db.models import EscalationStatus
from src.models.escalation import EscalationOut, ResolveRequest
from src.services import escalation_service

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
