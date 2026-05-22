from typing import Annotated
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from src.api.schemas.auth import UserCreate, UserResponse, Token, LoginRequest, TokenRefreshRequest
from src.services.auth import AuthService
from src.api.deps import DBDep

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: DBDep):
    auth_service = AuthService(db)
    return await auth_service.register(user_in)

@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBDep
):
    """
    Standard OAuth2 compatible login for Swagger UI.
    Use 'username' field for email.
    """
    auth_service = AuthService(db)
    return await auth_service.login(LoginRequest(email=form_data.username, password=form_data.password))

@router.post("/login-json", response_model=Token, include_in_schema=False)
async def login_json(login_data: LoginRequest, db: DBDep):
    """
    JSON-based login for programmatic access.
    """
    auth_service = AuthService(db)
    return await auth_service.login(login_data)

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_data: TokenRefreshRequest, db: DBDep):
    auth_service = AuthService(db)
    return await auth_service.refresh_token(refresh_data.refresh_token)
