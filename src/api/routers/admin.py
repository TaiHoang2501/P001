"""Developer-only endpoints, guarded by the X-Admin-Token header (ADMIN_API_TOKEN), not by a user role.

The AI kill switch belongs here, not in the Operator Console: the people who see that the assistant must stop
(wrong answers in the traces, the model provider failing, cost spikes, an attack) are the developers watching the
system. Operators only see whether the assistant is on (GET /operator/ai-assistant). Use scripts/ai_switch.py.
Hidden from the OpenAPI schema (the web app never calls these).
"""

from fastapi import APIRouter, Request

from src.config import get_settings
from src.core.deps import AdminToken, DbSession
from src.models.schemas import AssistantControlOut, AssistantToggle
from src.services import assistant_control, rate_limit

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[AdminToken], include_in_schema=False)


@router.get("/ai-assistant", response_model=AssistantControlOut)
def ai_assistant(db: DbSession) -> AssistantControlOut:
    return AssistantControlOut.model_validate(assistant_control.status(db))


@router.put("/ai-assistant", response_model=AssistantControlOut)
def set_ai_assistant(data: AssistantToggle, db: DbSession) -> AssistantControlOut:
    """Kill switch: turn the AI assistant off (buyers see the maintenance notice) or back on. Audited."""
    return AssistantControlOut.model_validate(assistant_control.set_enabled(db, None, data.enabled, data.reason))


@router.get("/diagnostics/client-ip")
def client_ip(request: Request) -> dict[str, str | int | None]:
    """After a deploy: which address guest rate limits use for this request. `client_ip` must be the caller's own
    public IP; if it is the platform's proxy instead, adjust TRUSTED_PROXY_HOPS / CLIENT_IP_HEADER."""
    settings = get_settings()
    return {
        "client_ip": rate_limit.client_ip(request),
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "client_ip_header": settings.client_ip_header or None,
        "trusted_proxy_hops": settings.trusted_proxy_hops,
    }
