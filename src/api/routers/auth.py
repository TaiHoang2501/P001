from fastapi import APIRouter

from src.core.deps import CurrentUser, DbSession
from src.models.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from src.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, db: DbSession) -> TokenResponse:
    return auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DbSession) -> TokenResponse:
    return auth_service.login(db, data)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
