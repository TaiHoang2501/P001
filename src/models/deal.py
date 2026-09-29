from datetime import datetime

from pydantic import BaseModel

from src.db.models import DealStatus


class DealOut(BaseModel):
    id: int
    code: str
    status: DealStatus
    property_id: int
    property_label: str
    buyer_id: int
    seller_id: int
    # Progressive disclosure level 1-4 (spec §4.7)
    disclosure_level: int
    created_at: datetime
    updated_at: datetime
