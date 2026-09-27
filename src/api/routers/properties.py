"""Public/customer property endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.core.actor import Actor
from src.core.deps import DbSession, get_current_user
from src.models.booking import SlotOut
from src.models.property import PropertyOut, SearchCriteria, SearchResult
from src.services import availability_service, property_service

router = APIRouter(tags=["properties"])

_optional_bearer = HTTPBearer(auto_error=False)


def optional_actor(
    db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_optional_bearer)]
) -> Actor | None:
    if credentials is None:
        return None
    return Actor(user=get_current_user(db, credentials))


class BuildingOut(BaseModel):
    id: int
    code: str
    name: str


class ProjectOut(BaseModel):
    id: int
    code: str
    name: str
    city: str
    buildings: list[BuildingOut]


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: DbSession) -> list[ProjectOut]:
    return [
        ProjectOut(
            id=p.id,
            code=p.code,
            name=p.name,
            city=p.city,
            buildings=[BuildingOut(id=b.id, code=b.code, name=b.name) for b in p.buildings],
        )
        for p in property_service.list_projects(db)
    ]


@router.post("/properties/search", response_model=SearchResult)
def search_properties(criteria: SearchCriteria, db: DbSession) -> SearchResult:
    return property_service.search(db, criteria)


@router.get("/properties/{property_id}", response_model=PropertyOut)
def get_property(
    property_id: int, db: DbSession, actor: Annotated[Actor | None, Depends(optional_actor)]
) -> PropertyOut:
    return property_service.get_property(db, property_id, actor)


@router.get("/properties/{property_id}/slots", response_model=list[SlotOut])
def free_slots(property_id: int, db: DbSession) -> list[SlotOut]:
    return availability_service.check_availability(db, property_id)["free_slots"]
