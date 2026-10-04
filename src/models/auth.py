import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.db.models import UserRole, UserStatus

PHONE_PATTERN = r"^0\d{9,10}$"
_PHONE_RE = re.compile(PHONE_PATTERN)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SelfServiceRole = Literal["CUSTOMER", "OWNER"]
# Password sign-up is for buyers only: sellers sign up and sign in with phone + OTP
PasswordSignupRole = Literal["CUSTOMER"]


def is_phone(target: str) -> bool:
    return _PHONE_RE.fullmatch(target) is not None


def _phone_or_email(value: str) -> str:
    value = value.strip().lower()
    if not (is_phone(value) or _EMAIL_RE.fullmatch(value)):
        raise ValueError("must be a Vietnamese phone number (e.g. 0901234567) or an email")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern=PHONE_PATTERN, description="Vietnamese phone, e.g. 0901234567")
    email: EmailStr | None = None
    password: str = Field(..., min_length=8, max_length=128)
    # Operators are created by admins/seed only; sellers use phone + OTP
    role: PasswordSignupRole = "CUSTOMER"


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, description="Phone or email")
    password: str = Field(..., min_length=1)


class OtpRequest(BaseModel):
    target: str = Field(..., description="Phone (buyer/seller) or email (seller) to send the code to")
    # The account kind being signed into: a phone already used by another kind is refused before any code is sent
    role: SelfServiceRole | None = None
    # "signup" = creating a new account: a phone that already has any account is refused (PHONE_IN_USE)
    purpose: Literal["login", "signup"] = "login"

    _check_target = field_validator("target")(_phone_or_email)


class OtpRequestResponse(BaseModel):
    expires_in: int = Field(..., description="Seconds until the code expires")
    # Only filled outside production, until an SMS/Zalo provider exists
    debug_code: str | None = None
    # With `role` on a login: the phone already has an account of that kind (no sign-up details needed)
    account_exists: bool = False


class OtpVerifyRequest(BaseModel):
    target: str
    code: str = Field(..., pattern=r"^\d{6}$")
    # Sign-up details, required only the first time this phone is used
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    # The account kind being signed into (and created on first use; buyer when omitted)
    role: SelfServiceRole | None = None

    _check_target = field_validator("target")(_phone_or_email)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    status: UserStatus
    full_name: str
    phone: str
    email: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
