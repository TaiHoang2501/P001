from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.db.models import UserRole, UserStatus

PHONE_PATTERN = r"^0\d{9,10}$"


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern=PHONE_PATTERN, description="Vietnamese phone, e.g. 0901234567")
    email: EmailStr | None = None
    password: str = Field(..., min_length=8, max_length=128)
    # Operators are created by admins/seed only
    role: Literal["CUSTOMER", "OWNER"] = "CUSTOMER"


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, description="Phone or email")
    password: str = Field(..., min_length=1)


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
