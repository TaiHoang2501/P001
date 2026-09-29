from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import AlreadyExistsError, InvalidCredentialsError
from src.core.security import create_access_token, hash_password, verify_password
from src.db.models import User, UserRole, UserStatus
from src.models.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from src.services import audit


def register(db: Session, data: RegisterRequest) -> TokenResponse:
    conditions = [User.phone == data.phone]
    if data.email:
        conditions.append(User.email == data.email.lower())
    if db.scalar(select(User.id).where(or_(*conditions))) is not None:
        raise AlreadyExistsError("Phone or email is already registered")

    user = User(
        role=UserRole(data.role),
        # MVP: owners are active immediately; their listings still need operator approval
        status=UserStatus.ACTIVE,
        full_name=data.full_name.strip(),
        phone=data.phone,
        email=data.email.lower() if data.email else None,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.flush()
    audit.record(db, Actor(user=user), "user.register", "user", user.id, after={"role": user.role.value})
    db.commit()
    return _token_for(user)


def login(db: Session, data: LoginRequest) -> TokenResponse:
    identifier = data.identifier.strip().lower()
    user = db.scalar(select(User).where(or_(User.phone == identifier, User.email == identifier)))
    # Same error for unknown user and wrong password: don't reveal which accounts exist
    if user is None or not verify_password(data.password, user.password_hash):
        raise InvalidCredentialsError("Wrong phone/email or password")
    if user.status == UserStatus.SUSPENDED:
        raise InvalidCredentialsError("Account is suspended")
    return _token_for(user)


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        user=UserOut.model_validate(user),
    )
