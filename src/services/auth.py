from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    decode_token
)
from src.db.models import User, RefreshToken
from src.repositories.user import UserRepository
from src.repositories.auth import RefreshTokenRepository
from src.api.schemas.auth import UserCreate, Token, LoginRequest
from src.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = RefreshTokenRepository(session)

    async def register(self, user_in: UserCreate) -> User:
        existing_user = await self.user_repo.get_by_email(user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        user = User(
            email=user_in.email,
            password_hash=get_password_hash(user_in.password)
        )
        await self.user_repo.create(user)
        await self.session.commit()
        logger.info("user_registered", email=user.email, user_id=str(user.id))
        return user

    async def login(self, login_data: LoginRequest) -> Token:
        user = await self.user_repo.get_by_email(login_data.email)
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(subject=user.id)
        refresh_token_str = create_refresh_token(subject=user.id)
        
        # Save refresh token to DB
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db_refresh_token = RefreshToken(
            token=refresh_token_str,
            user_id=user.id,
            expires_at=expires_at
        )
        await self.token_repo.create(db_refresh_token)
        await self.session.commit()
        
        logger.info("user_logged_in", user_id=str(user.id))
        return Token(
            access_token=access_token,
            refresh_token=refresh_token_str
        )

    async def refresh_token(self, refresh_token: str) -> Token:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
            user_id = payload.get("sub")
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        
        db_token = await self.token_repo.get_by_token(refresh_token)
        if not db_token or db_token.revoked or db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            if db_token and not db_token.revoked:
                # Potential reuse attack or just expired. In production, you might revoke all user tokens here.
                await self.token_repo.revoke_user_tokens(db_token.user_id)
                await self.session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired")
        
        # Revoke old token and issue new pair (Refresh Token Rotation)
        db_token.revoked = True
        
        access_token = create_access_token(subject=user_id)
        new_refresh_token_str = create_refresh_token(subject=user_id)
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        new_db_token = RefreshToken(
            token=new_refresh_token_str,
            user_id=db_token.user_id,
            expires_at=expires_at
        )
        await self.token_repo.create(new_db_token)
        await self.session.commit()
        
        logger.info("token_refreshed", user_id=str(db_token.user_id))
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token_str
        )
