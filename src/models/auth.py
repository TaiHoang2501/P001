import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.db.models import UserRole, UserStatus

# A Vietnamese mobile number (the sign-in code goes to it by SMS): 10 digits, 03 / 05 / 07 / 08 / 09
# ("0012345678" or "0123456789" is not one)
PHONE_PATTERN = r"^0[35789]\d{8}$"
_PHONE_RE = re.compile(PHONE_PATTERN)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SelfServiceRole = Literal["CUSTOMER", "OWNER"]
# Password sign-up is for buyers only: sellers sign up and sign in with phone + OTP


def is_phone(target: str) -> bool:
    return _PHONE_RE.fullmatch(target) is not None


def normalize_phone(value: str) -> str:
    """ "0912 345 678", "0912.345.678", "+84 912 345 678", "84912345678" -> "0912345678"; other text unchanged."""
    if not re.fullmatch(r"[+\d\s.\-()]+", value):
        return value
    digits = re.sub(r"\D", "", value)
    if digits.startswith("84") and len(digits) in (11, 12):
        digits = "0" + digits[2:]
    return digits


def _phone_or_email(value: str) -> str:
    value = normalize_phone(value.strip().lower())
    if not (is_phone(value) or _EMAIL_RE.fullmatch(value)):
        raise ValueError("must be a Vietnamese phone number (e.g. 09xxxxxxxx) or an email")
    return value


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


OtpProvider = Literal["local", "firebase"]


class FirebaseWebConfig(BaseModel):
    """Public Firebase web app config: the browser sends and checks the SMS code with Firebase Phone Auth."""

    api_key: str
    auth_domain: str
    project_id: str


class OtpRequestResponse(BaseModel):
    expires_in: int = Field(..., description="Seconds until the code expires")
    # "local": we made a code (check it with `code`); "firebase": nothing was sent yet, the browser now has
    # Firebase send the SMS (with `firebase`) and verifies with `firebase_id_token`
    provider: OtpProvider = "local"
    firebase: FirebaseWebConfig | None = None
    # Local codes only, outside production (no SMS is sent for them)
    debug_code: str | None = None
    # A demo account's phone: no SMS was sent, `debug_code` is its fixed code (fill it in for the tester)
    demo: bool = False
    # With `role` on a login: the phone already has an account of that kind (no sign-up details needed)
    account_exists: bool = False


class OtpVerifyRequest(BaseModel):
    target: str
    # Exactly one: the code we sent (OTP_PROVIDER=local) or the ID token of a Firebase phone sign-in (firebase)
    code: str | None = Field(default=None, pattern=r"^\d{6}$")
    firebase_id_token: str | None = Field(default=None, min_length=20, max_length=4096)
    # Sign-up details, required only the first time this phone is used
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    # The account kind being signed into (and created on first use; buyer when omitted)
    role: SelfServiceRole | None = None

    _check_target = field_validator("target")(_phone_or_email)

    @model_validator(mode="after")
    def _one_proof(self) -> "OtpVerifyRequest":
        if (self.code is None) == (self.firebase_id_token is None):
            raise ValueError("send either code or firebase_id_token")
        return self


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
