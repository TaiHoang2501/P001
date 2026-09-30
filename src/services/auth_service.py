from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import AccountNotFoundError, AlreadyExistsError, ForbiddenError, InvalidCredentialsError
from src.core.security import create_access_token, hash_password, verify_password
from src.db.models import BuyerProfile, SellerProfile, User, UserRole, UserStatus
from src.models.auth import (
    LoginRequest,
    OtpRequest,
    OtpRequestResponse,
    OtpVerifyRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    is_phone,
)
from src.services import audit, otp_service


def register(db: Session, data: RegisterRequest) -> TokenResponse:
    conditions = [User.phone == data.phone]
    if data.email:
        conditions.append(User.email == data.email.lower())
    if db.scalar(select(User.id).where(or_(*conditions))) is not None:
        raise AlreadyExistsError("Phone or email is already registered")

    user = _create_user(
        db,
        role=UserRole(data.role),
        full_name=data.full_name,
        phone=data.phone,
        email=data.email.lower() if data.email else None,
        password_hash=hash_password(data.password),
    )
    db.commit()
    return _token_for(user)


def login(db: Session, data: LoginRequest) -> TokenResponse:
    identifier = data.identifier.strip().lower()
    user = db.scalar(select(User).where(or_(User.phone == identifier, User.email == identifier)))
    # Same error for unknown user, OTP-only account (every seller) and wrong password: don't reveal which accounts exist
    if (
        user is None
        or user.password_hash is None
        or user.role == UserRole.OWNER
        or not verify_password(data.password, user.password_hash)
    ):
        raise InvalidCredentialsError("Wrong phone/email or password")
    if user.status == UserStatus.SUSPENDED:
        raise InvalidCredentialsError("Account is suspended")
    return _token_for(user)


def request_otp(db: Session, data: OtpRequest) -> OtpRequestResponse:
    code, ttl = otp_service.request_code(db, data.target)
    debug_code = None if get_settings().app_env == "production" else code
    return OtpRequestResponse(expires_in=ttl, debug_code=debug_code)


def verify_otp(db: Session, data: OtpVerifyRequest) -> TokenResponse:
    """Log in with a valid OTP; the first time a phone is used, sign up with `full_name` + `role`."""
    otp = otp_service.check_code(db, data.target, data.code)
    user = db.scalar(select(User).where(or_(User.phone == data.target, User.email == data.target)))

    if user is None:
        # The code stays valid so the client can resend it together with the sign-up details
        if data.full_name is None:
            raise AccountNotFoundError("No account for this phone yet; send full_name and role to sign up")
        if not is_phone(data.target):
            raise AccountNotFoundError("Sign up with a phone number; email can be added later")
        user = _create_user(db, role=UserRole(data.role), full_name=data.full_name, phone=data.target)
    elif user.role == UserRole.INVESTOR_OPERATOR:
        raise ForbiddenError("Operators sign in with email and password")
    elif user.role == UserRole.OWNER and not is_phone(data.target):
        raise ForbiddenError("Sellers sign in with their phone number")
    elif user.status == UserStatus.SUSPENDED:
        raise InvalidCredentialsError("Account is suspended")

    otp_service.consume(otp)
    db.commit()
    return _token_for(user)


def _create_user(
    db: Session,
    *,
    role: UserRole,
    full_name: str,
    phone: str,
    email: str | None = None,
    password_hash: str | None = None,
) -> User:
    user = User(
        role=role,
        # Accounts are active immediately; sellers still need verification before their listings go live
        status=UserStatus.ACTIVE,
        full_name=full_name.strip(),
        phone=phone,
        email=email,
        password_hash=password_hash,
    )
    db.add(user)
    db.flush()
    if role == UserRole.CUSTOMER:
        db.add(BuyerProfile(user_id=user.id))
    elif role == UserRole.OWNER:
        db.add(SellerProfile(user_id=user.id))
    audit.record(db, Actor(user=user), "user.register", "user", user.id, after={"role": user.role.value})
    return user


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        user=UserOut.model_validate(user),
    )
