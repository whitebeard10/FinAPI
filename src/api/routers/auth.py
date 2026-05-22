from fastapi import APIRouter, Depends, status
from src.api.schemas.auth import UserCreate, UserResponse, Token, LoginRequest, TokenRefreshRequest
from src.services.auth import AuthService
from src.api.deps import DBDep

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: DBDep):
    auth_service = AuthService(db)
    return await auth_service.register(user_in)

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: DBDep):
    auth_service = AuthService(db)
    return await auth_service.login(login_data)

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_data: TokenRefreshRequest, db: DBDep):
    auth_service = AuthService(db)
    return await auth_service.refresh_token(refresh_data.refresh_token)
