"""Structured business errors shared by the REST API and the AI tools.

Every error has a stable machine-readable `code` so the React UI and the agent
can react to it (e.g. SLOT_UNAVAILABLE -> suggest another slot).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class NotAuthenticatedError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "INVALID_CREDENTIALS"


class AccountNotFoundError(AppError):
    """OTP was valid but no account exists yet: the client should ask for sign-up details."""

    status_code = 404
    code = "ACCOUNT_NOT_FOUND"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class AlreadyExistsError(AppError):
    status_code = 409
    code = "ALREADY_EXISTS"


class PhoneInUseError(AppError):
    """The phone/email already belongs to another kind of account (e.g. a seller's phone on the buyer sign-up)."""

    status_code = 409
    code = "PHONE_IN_USE"


class StateConflictError(AppError):
    """Requested action is not allowed from the record's current status (F10)."""

    status_code = 409
    code = "STATE_CONFLICT"


class SlotUnavailableError(AppError):
    """The time window was taken by someone else (F3 / F5)."""

    status_code = 409
    code = "SLOT_UNAVAILABLE"


class BusinessRuleViolationError(AppError):
    status_code = 422
    code = "BUSINESS_RULE_VIOLATION"


class SellerUnverifiedError(AppError):
    """The property's owner is not verified, so it cannot be listed or booked (AC-04)."""

    status_code = 422
    code = "SELLER_UNVERIFIED"


class OwnershipNotMatchedError(AppError):
    """Holder name + red book code do not match the investor's records (same answer for both, to not leak which)."""

    status_code = 422
    code = "OWNERSHIP_NOT_MATCHED"


class OwnershipOtpInvalidError(AppError):
    """Wrong or expired ownership OTP. Not 401: the seller's session itself is fine."""

    status_code = 422
    code = "OTP_INVALID"


class AgentUnavailableError(AppError):
    """The AI assistant cannot answer right now (not configured, or the model provider failed)."""

    status_code = 503
    code = "AGENT_UNAVAILABLE"


class AiDisabledError(AppError):
    """An operator turned the AI assistant off (kill switch); the message names the support hotline."""

    status_code = 503
    code = "AI_DISABLED"


class StorageUnavailableError(AppError):
    """Media storage is not configured or the storage provider failed."""

    status_code = 503
    code = "STORAGE_UNAVAILABLE"


class OtpUnavailableError(AppError):
    """The sign-in code provider (Firebase) cannot be reached or is not configured."""

    status_code = 503
    code = "OTP_UNAVAILABLE"


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})
