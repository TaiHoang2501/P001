from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.db.models import (
    Direction,
    Furnishing,
    LegalStatus,
    MediaKind,
    PropertyStatus,
    PropertyType,
    ViewType,
)

Priority = Literal["high", "normal", "low"]


class PropertyBase(BaseModel):
    building_id: int
    unit_code: str = Field(..., min_length=1, max_length=50)
    property_type: PropertyType
    bedrooms: int = Field(..., ge=0, le=20)
    bathrooms: int = Field(..., ge=0, le=20)
    area_m2: Decimal = Field(..., gt=0, le=10000)
    floor: int = Field(..., ge=-5, le=200)
    price_vnd: int = Field(..., gt=0)
    direction: Direction
    view: ViewType
    furnishing: Furnishing
    legal_status: LegalStatus
    description: str = Field(default="", max_length=5000)


class PropertyCreate(PropertyBase):
    # A red book the seller verified (red book + OTP) and no other listing uses yet
    verification_id: int


class PropertyUpdate(BaseModel):
    """Partial update; only allowed while the listing is DRAFT or REJECTED."""

    unit_code: str | None = Field(default=None, min_length=1, max_length=50)
    property_type: PropertyType | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=20)
    bathrooms: int | None = Field(default=None, ge=0, le=20)
    area_m2: Decimal | None = Field(default=None, gt=0, le=10000)
    floor: int | None = Field(default=None, ge=-5, le=200)
    price_vnd: int | None = Field(default=None, gt=0)
    direction: Direction | None = None
    view: ViewType | None = None
    furnishing: Furnishing | None = None
    legal_status: LegalStatus | None = None
    description: str | None = Field(default=None, max_length=5000)


class MediaCreate(BaseModel):
    kind: MediaKind
    # Key of the object already uploaded to S3
    s3_key: str = Field(..., min_length=3, max_length=512)
    content_type: str = Field(..., min_length=3, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=1000)
    # Ignored for OWNERSHIP_DOC, which is always private
    is_public: bool = True


class MediaOut(BaseModel):
    id: int
    kind: MediaKind
    url: str
    content_type: str
    sort_order: int
    is_public: bool


class PropertyOut(PropertyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    status: PropertyStatus
    project_code: str
    project_name: str
    building_name: str
    city: str
    rejection_reason: str | None = None
    created_at: datetime
    # Buyers only get public media; the owner and operators also see private documents
    media: list[MediaOut] = Field(default_factory=list)
    # Public image URLs in display order (derived from media)
    image_urls: list[str] = Field(default_factory=list)


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


# ---------- Search / recommendation ----------


class SearchCriteria(BaseModel):
    """Structured customer preference (spec §4.5 / §4.6).

    Hard constraints remove candidates; preferred_* fields only affect the score.
    """

    # Hard constraints
    project_codes: list[str] | None = Field(default=None, description="e.g. ['VHOP1', 'VHSC']")
    property_types: list[PropertyType] | None = None
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, gt=0)
    bedrooms_min: int | None = Field(default=None, ge=0)
    area_min: Decimal | None = Field(default=None, gt=0)
    keyword: str | None = Field(default=None, max_length=200, description="Fuzzy match on description")

    # Soft preferences
    preferred_bedrooms: int | None = Field(default=None, ge=0)
    preferred_area_m2: Decimal | None = Field(default=None, gt=0)
    preferred_directions: list[Direction] | None = None
    preferred_views: list[ViewType] | None = None
    preferred_furnishing: Furnishing | None = None
    preferred_floor_min: int | None = None
    preferred_floor_max: int | None = None
    priorities: dict[str, Priority] = Field(
        default_factory=dict,
        description="Per-criterion priority: keys price|area|bedrooms|direction|view|floor|furnishing",
    )

    limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def _check_ranges(self) -> "SearchCriteria":
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min must be <= budget_max")
        if (
            self.preferred_floor_min is not None
            and self.preferred_floor_max is not None
            and self.preferred_floor_min > self.preferred_floor_max
        ):
            raise ValueError("preferred_floor_min must be <= preferred_floor_max")
        return self


class CriterionMatch(BaseModel):
    criterion: str
    matched: bool
    score: float = Field(..., ge=0, le=1)
    wanted: str
    actual: str


class Recommendation(BaseModel):
    property: PropertyOut
    match_score: float = Field(..., ge=0, le=1)
    matched: list[CriterionMatch]
    unmatched: list[CriterionMatch]


class SearchResult(BaseModel):
    total_candidates: int = Field(..., description="Properties passing hard constraints")
    results: list[Recommendation]
