"""LangChain tools the agent can call, wrapping the agent tool contract (src/services/agent_api.py).

- The buyer's user_id is read from the run config set by the chat endpoint (JWT), never
  from model arguments, so the model cannot act on behalf of another user.
- Each tool returns (content, artifact): the model reads the JSON content, the chat service
  reads the artifact envelope to render recommendation cards and booking updates.
- There is intentionally no tool to confirm a viewing or to create/release a hold (AC-05, §4.13).
"""

import json
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from src.models.property import SearchCriteria
from src.services import agent_api, buyer_memory

Result = tuple[str, agent_api.Envelope]


def _result(envelope: agent_api.Envelope) -> Result:
    return json.dumps(envelope, ensure_ascii=False, default=str), envelope


def _user_id(config: RunnableConfig) -> int | None:
    return config.get("configurable", {}).get("user_id")


_NO_SESSION: agent_api.Envelope = {
    "ok": False,
    "error": {"code": "UNAUTHENTICATED", "message": "No authenticated buyer in this chat", "details": {}},
}


class _Window(BaseModel):
    start_at: str = Field(..., description="ISO 8601 with timezone, e.g. 2026-10-03T14:00:00+07:00")
    end_at: str = Field(..., description="ISO 8601 with timezone")


class _AvailabilityArgs(BaseModel):
    property_id: int
    buyer_windows: list[_Window] = Field(..., min_length=1, description="When the buyer is free")


class _ViewingRequestArgs(BaseModel):
    property_id: int
    start_at: str = Field(..., description="One of the proposals from check_property_availability (ISO 8601)")
    buyer_windows: list[_Window] = Field(default_factory=list, description="The buyer's free windows, if known")
    note: str | None = Field(default=None, max_length=1000)


class _EscalationArgs(BaseModel):
    type: Literal["NO_COMMON_SLOT", "SCHEDULE_CONFLICT", "PROPERTY_ISSUE", "OTHER"]
    summary: str = Field(..., min_length=5, max_length=2000, description="What the buyer needs, in Vietnamese")
    property_id: int | None = None
    booking_id: int | None = None


class _RescheduleArgs(BaseModel):
    booking_id: int
    start_at: str = Field(..., description="New start time from check_property_availability (ISO 8601)")


@tool(response_format="content_and_artifact")
def list_projects() -> Result:
    """List the Vinhomes projects on the platform with their codes (use codes in search_properties.project_codes)."""
    return _result(agent_api.list_projects())


@tool(response_format="content_and_artifact", args_schema=SearchCriteria)
def search_properties(config: RunnableConfig, **criteria: Any) -> Result:
    """Find AVAILABLE Vinhomes properties of verified sellers matching the buyer's needs, ranked by match score.

    Money is in VND (3,5 tỷ = 3500000000). Hard constraints (project_codes, property_types,
    budget_min/budget_max, bedrooms_min, area_min, keyword) remove properties; preferred_* fields
    only affect ranking. Each result explains which preferences matched and which did not.
    """
    envelope = agent_api.search_properties(criteria)
    # Remember the signed-in buyer's needs for later conversations
    if envelope.get("ok") and (user_id := _user_id(config)) is not None:
        buyer_memory.remember_criteria(user_id, criteria)
    return _result(envelope)


@tool(response_format="content_and_artifact")
def get_property_detail(property_id: int) -> Result:
    """Full details of one AVAILABLE property (description, legal status, furnishing, photos)."""
    return _result(agent_api.get_property_detail(property_id))


@tool(response_format="content_and_artifact")
def get_seller_status(property_id: int) -> Result:
    """Whether the property's seller has been verified by the investor. Contains no seller contact details."""
    return _result(agent_api.get_seller_status(property_id))


@tool(response_format="content_and_artifact")
def check_seller_availability(property_id: int) -> Result:
    """The seller's upcoming free viewing windows for a property (times already booked or held are removed)."""
    return _result(agent_api.check_seller_availability(property_id))


@tool(response_format="content_and_artifact", args_schema=_AvailabilityArgs)
def check_property_availability(property_id: int, buyer_windows: list[Any], config: RunnableConfig) -> Result:
    """Match the buyer's free windows with the seller's availability.

    Returns up to 3 `proposals` (viewing start/end times) inside the common windows. If `proposals`
    is empty there is no common slot: offer the `alternatives` (seller's next free times) instead.
    """
    windows = [w.model_dump() if isinstance(w, BaseModel) else w for w in buyer_windows]
    envelope = agent_api.check_property_availability(property_id, windows)
    # Remember when the signed-in buyer is free, so the next property needs no new question
    if envelope.get("ok") and (user_id := _user_id(config)) is not None:
        buyer_memory.remember_windows(user_id, windows)
    return _result(envelope)


@tool(response_format="content_and_artifact")
def get_deal_status(config: RunnableConfig, deal_id: int | None = None) -> Result:
    """The buyer's deals (one Deal per property they asked to view) and their status."""
    user_id = _user_id(config)
    if user_id is None:
        return _result(_NO_SESSION)
    return _result(agent_api.get_deal_status(user_id, deal_id))


@tool(response_format="content_and_artifact")
def get_booking_status(config: RunnableConfig, booking_id: int | None = None) -> Result:
    """The buyer's viewing requests and their status (one booking, or all when booking_id is omitted)."""
    user_id = _user_id(config)
    if user_id is None:
        return _result(_NO_SESSION)
    return _result(agent_api.get_booking_status(user_id, booking_id))


@tool(response_format="content_and_artifact", args_schema=_ViewingRequestArgs)
def create_viewing_request(
    property_id: int,
    start_at: str,
    config: RunnableConfig,
    buyer_windows: list[Any] | None = None,
    note: str | None = None,
) -> Result:
    """Send a viewing request to the seller for one proposed time. Only call this after the buyer explicitly
    chose that property and time. It opens a Deal (code VH-...) and the request is NOT confirmed until the
    seller (owner) confirms it."""
    user_id = _user_id(config)
    if user_id is None:
        return _result(_NO_SESSION)
    windows = [w.model_dump() if isinstance(w, BaseModel) else w for w in buyer_windows or []]
    return _result(
        agent_api.create_viewing_request(user_id, property_id, start_at=start_at, buyer_windows=windows, note=note)
    )


@tool(response_format="content_and_artifact")
def cancel_viewing(booking_id: int, config: RunnableConfig) -> Result:
    """Cancel one of the buyer's own viewing requests. Only call after the buyer confirms they want to cancel."""
    user_id = _user_id(config)
    if user_id is None:
        return _result(_NO_SESSION)
    return _result(agent_api.cancel_viewing(user_id, booking_id))


@tool(response_format="content_and_artifact", args_schema=_RescheduleArgs)
def reschedule_viewing(booking_id: int, start_at: str, config: RunnableConfig) -> Result:
    """Ask the seller to move a CONFIRMED viewing to a new time. The viewing stays at the old time until
    the seller confirms the new one."""
    user_id = _user_id(config)
    if user_id is None:
        return _result(_NO_SESSION)
    return _result(agent_api.reschedule_viewing(user_id, booking_id, start_at))


@tool(response_format="content_and_artifact", args_schema=_EscalationArgs)
def create_human_escalation(
    type: str,
    summary: str,
    config: RunnableConfig,
    property_id: int | None = None,
    booking_id: int | None = None,
) -> Result:
    """Hand the case to a human operator of the investor. Use when there is still no workable viewing time
    after offering alternatives (NO_COMMON_SLOT), a schedule conflict you cannot solve, a problem with the
    property's information (PROPERTY_ISSUE), or when the buyer asks for a person."""
    user_id = _user_id(config)
    if user_id is None:
        return _result(_NO_SESSION)
    thread_id = config.get("configurable", {}).get("thread_id")
    return _result(
        agent_api.create_human_escalation(
            user_id, type, summary, property_id=property_id, booking_id=booking_id, thread_id=thread_id
        )
    )


TOOLS: list[BaseTool] = [
    list_projects,
    search_properties,
    get_property_detail,
    get_seller_status,
    check_seller_availability,
    check_property_availability,
    get_deal_status,
    get_booking_status,
    create_viewing_request,
    cancel_viewing,
    reschedule_viewing,
    create_human_escalation,
]
