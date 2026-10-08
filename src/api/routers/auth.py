from fastapi import APIRouter

from src.core.deps import CurrentUser, DbSession
from src.models.auth import (
    LoginRequest,
    OtpRequest,
    OtpRequestResponse,
    OtpVerifyRequest,
    TokenResponse,
    UserOut,
)
from src.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DbSession) -> TokenResponse:
    """Password login: investor / operator accounts only. Buyers and sellers sign in with phone + OTP."""
    return auth_service.login(db, data)


@router.post("/otp/request", response_model=OtpRequestResponse, status_code=202)
def request_otp(data: OtpRequest, db: DbSession) -> OtpRequestResponse:
    return auth_service.request_otp(db, data)


@router.post("/otp/verify", response_model=TokenResponse)
def verify_otp(data: OtpVerifyRequest, db: DbSession) -> TokenResponse:
    """Buyer/Seller login with the code; the first use of a phone signs up (needs full_name + role)."""
    return auth_service.verify_otp(db, data)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
