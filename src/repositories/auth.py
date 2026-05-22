from typing import Optional, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import RefreshToken
from src.repositories.base import BaseRepository

class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, session: AsyncSession):
        super().__init__(RefreshToken, session)

    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        query = select(RefreshToken).where(RefreshToken.token == token)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def revoke_user_tokens(self, user_id: Any):
        query = select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
        result = await self.session.execute(query)
        tokens = result.scalars().all()
        for token in tokens:
            token.revoked = True
        await self.session.flush()
