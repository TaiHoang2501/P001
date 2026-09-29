from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import ForbiddenError, NotAuthenticatedError
from src.core.security import decode_access_token
from src.db.models import User, UserRole, UserStatus
from src.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise NotAuthenticatedError("Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as e:
        raise NotAuthenticatedError("Invalid or expired token") from e

    user = db.get(User, int(payload["sub"]))
    if user is None or user.status == UserStatus.SUSPENDED:
        raise NotAuthenticatedError("Account not found or suspended")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_actor(user: CurrentUser) -> Actor:
    return Actor(user=user)


def require_role(*roles: UserRole) -> Callable[[User], Actor]:
    """Dependency factory: only the given roles may call the endpoint (403 otherwise)."""

    def _check(user: CurrentUser) -> Actor:
        if user.role not in roles:
            raise ForbiddenError(f"This action requires role: {', '.join(r.value for r in roles)}")
        return Actor(user=user)

    return _check


CustomerActor = Annotated[Actor, Depends(require_role(UserRole.CUSTOMER))]
OwnerActor = Annotated[Actor, Depends(require_role(UserRole.OWNER))]
OperatorActor = Annotated[Actor, Depends(require_role(UserRole.INVESTOR_OPERATOR))]
AnyActor = Annotated[Actor, Depends(get_actor)]
