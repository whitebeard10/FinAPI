import uuid
from typing import List
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Wallet, User
from src.repositories.wallet import WalletRepository
from src.api.schemas.wallet import WalletCreate
import structlog

logger = structlog.get_logger(__name__)

class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.wallet_repo = WalletRepository(session)

    async def create_wallet(self, user: User, wallet_in: WalletCreate) -> Wallet:
        wallet = Wallet(
            user_id=user.id,
            currency=wallet_in.currency,
            balance=Decimal("0.0")
        )
        await self.wallet_repo.create(wallet)
        await self.session.commit()
        logger.info("wallet_created", user_id=str(user.id), wallet_id=str(wallet.id))
        return wallet

    async def get_user_wallets(self, user_id: uuid.UUID) -> List[Wallet]:
        return await self.wallet_repo.get_user_wallets(user_id)
    
    async def get_wallet(self, wallet_id: uuid.UUID, user_id: uuid.UUID) -> Wallet:
        wallet = await self.wallet_repo.get(wallet_id)
        if not wallet or wallet.user_id != user_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Wallet not found")
        return wallet

    async def deposit(self, wallet_id: uuid.UUID, user_id: uuid.UUID, amount: Decimal) -> Wallet:
        wallet = await self.get_wallet(wallet_id, user_id)
        wallet.balance += amount
        await self.session.commit()
        logger.info("funds_deposited", wallet_id=str(wallet_id), amount=str(amount))
        return wallet
