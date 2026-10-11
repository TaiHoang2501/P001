from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import (
    AccountNotFoundError,
    InvalidCredentialsError,
    PhoneInUseError,
)
from src.core.security import create_access_token, verify_password
from src.db.models import BuyerProfile, SellerProfile, User, UserRole, UserStatus
from src.models.auth import (
    LoginRequest,
    OtpRequest,
    OtpRequestResponse,
    OtpVerifyRequest,
    TokenResponse,
    UserOut,
    is_phone,
)
from src.services import audit, otp_service


def login(db: Session, data: LoginRequest) -> TokenResponse:
    identifier = data.identifier.strip().lower()
    user = db.scalar(select(User).where(or_(User.phone == identifier, User.email == identifier)))
    # Only operators sign in with a password; buyers and sellers use phone + OTP. Same error for an unknown user,
    # a buyer / seller account and a wrong password: the answer never reveals which accounts exist
    if (
        user is None
        or user.password_hash is None
        or user.role != UserRole.INVESTOR_OPERATOR
        or not verify_password(data.password, user.password_hash)
    ):
        raise InvalidCredentialsError("Wrong phone/email or password")
    if user.status == UserStatus.SUSPENDED:
        raise InvalidCredentialsError("Account is suspended")
    return _token_for(user)


def _account_for(db: Session, target: str) -> User | None:
    target = target.strip().lower()
    return db.scalar(select(User).where(or_(User.phone == target, User.email == target)))


def _require_same_role(user: User | None, role: str | None) -> None:
    if user is not None and role is not None and user.role.value != role:
        raise PhoneInUseError(
            "This phone is already registered to another kind of account; use another number",
            # Which area to sign in to instead (buyer / seller); an operator's phone is not named as such
            details={"account_role": user.role.value} if user.role != UserRole.INVESTOR_OPERATOR else {},
        )


def request_otp(db: Session, data: OtpRequest) -> OtpRequestResponse:
    user = _account_for(db, data.target)
    # Say so before sending a code: a new account needs a phone nobody uses yet...
    if data.purpose == "signup" and user is not None:
        raise PhoneInUseError("This phone is already registered; sign up with another number or sign in")
    # ...and a seller's or operator's phone cannot sign in as a buyer (and back)
    _require_same_role(user, data.role)
    code, ttl = otp_service.request_code(db, data.target)
    debug_code = code if get_settings().otp_code_visible else None
    return OtpRequestResponse(
        expires_in=ttl, debug_code=debug_code, account_exists=data.role is not None and user is not None
    )


def verify_otp(db: Session, data: OtpVerifyRequest) -> TokenResponse:
    """Log in with a valid OTP; the first time a phone is used, sign up with `full_name` + `role`."""
    otp = otp_service.check_code(db, data.target, data.code)
    user = db.scalar(select(User).where(or_(User.phone == data.target, User.email == data.target)))
    _require_same_role(user, data.role)

    if user is None:
        # The code stays valid so the client can resend it together with the sign-up details
        if data.full_name is None:
            raise AccountNotFoundError("No account for this phone yet; send full_name and role to sign up")
        if not is_phone(data.target):
            raise AccountNotFoundError("Sign up with a phone number; email can be added later")
        user = _create_user(db, role=UserRole(data.role or "CUSTOMER"), full_name=data.full_name, phone=data.target)
    elif user.role == UserRole.INVESTOR_OPERATOR or (user.role == UserRole.OWNER and not is_phone(data.target)):
        # Operators use email + password, sellers their phone. Same neutral answer as a wrong code, so this form
        # never tells which numbers belong to an operator (no account enumeration)
        raise InvalidCredentialsError("This phone number or email cannot be used to sign in here")
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
