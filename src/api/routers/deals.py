"""Deal tracking for buyers, sellers and operators (spec §4.9)."""

from fastapi import APIRouter

from src.core.deps import AnyActor, DbSession
from src.db.models import DealStatus
from src.models.deal import DealOut
from src.services import deal_service

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("", response_model=list[DealOut])
def list_deals(actor: AnyActor, db: DbSession, status: DealStatus | None = None) -> list[DealOut]:
    return deal_service.list_for(db, actor, status)


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(deal_id: int, actor: AnyActor, db: DbSession) -> DealOut:
    return deal_service.get(db, actor, deal_id)
