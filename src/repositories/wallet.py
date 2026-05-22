import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Wallet
from src.repositories.base import BaseRepository

class WalletRepository(BaseRepository[Wallet]):
    def __init__(self, session: AsyncSession):
        super().__init__(Wallet, session)

    async def get_user_wallets(self, user_id: uuid.UUID) -> List[Wallet]:
        query = select(Wallet).where(Wallet.user_id == user_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_for_update(self, wallet_id: uuid.UUID) -> Optional[Wallet]:
        """
        Locks the wallet row for update.
        """
        query = select(Wallet).where(Wallet.id == wallet_id).with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_multiple_for_update(self, wallet_ids: List[uuid.UUID]) -> List[Wallet]:
        """
        Locks multiple wallet rows for update, sorted by ID to prevent deadlocks.
        """
        sorted_ids = sorted(wallet_ids)
        query = select(Wallet).where(Wallet.id.in_(sorted_ids)).order_by(Wallet.id).with_for_update()
        result = await self.session.execute(query)
        return list(result.scalars().all())
