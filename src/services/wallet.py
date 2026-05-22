import uuid
import hashlib
import json
from typing import List
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import Wallet, User, Transaction, TransactionStatus, IdempotencyRecord, AuditLog
from src.repositories.wallet import WalletRepository
from src.repositories.transaction import TransactionRepository, IdempotencyRepository
from src.api.schemas.wallet import WalletCreate, WalletDeposit
import structlog

logger = structlog.get_logger(__name__)

class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.wallet_repo = WalletRepository(session)
        self.transaction_repo = TransactionRepository(session)
        self.idempotency_repo = IdempotencyRepository(session)

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
            raise HTTPException(status_code=404, detail="Wallet not found")
        return wallet

    async def deposit(self, wallet_id: uuid.UUID, user: User, deposit_in: WalletDeposit) -> Wallet:
        # 1. Idempotency Check
        request_hash = self._generate_request_hash(deposit_in)
        existing_idempotency = await self.idempotency_repo.get_by_key(deposit_in.idempotency_key, user.id)
        
        if existing_idempotency:
            if existing_idempotency.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Idempotency key reused with different request parameters"
                )
            logger.info("deposit_idempotency_hit", key=deposit_in.idempotency_key)
            return await self.get_wallet(wallet_id, user.id)

        try:
            # 2. Lock Wallet
            wallet = await self.wallet_repo.get_for_update(wallet_id)
            if not wallet or wallet.user_id != user.id:
                raise HTTPException(status_code=404, detail="Wallet not found")

            transaction_ref = f"DEP-{uuid.uuid4().hex[:12].upper()}"

            # 3. Execute Balance Update
            wallet.balance += deposit_in.amount
            
            # 4. Create Transaction Record
            transaction = Transaction(
                transaction_reference=transaction_ref,
                source_wallet_id=None, # Deposit has no source wallet in-system
                destination_wallet_id=wallet_id,
                amount=deposit_in.amount,
                currency=wallet.currency,
                status=TransactionStatus.COMPLETED,
                idempotency_key=deposit_in.idempotency_key,
                completed_at=datetime.now(timezone.utc)
            )
            await self.transaction_repo.create(transaction)

            # 5. Create Idempotency Record
            idempotency_record = IdempotencyRecord(
                idempotency_key=deposit_in.idempotency_key,
                user_id=user.id,
                request_hash=request_hash,
                response_code=200,
                response_body={"wallet_id": str(wallet.id), "new_balance": str(wallet.balance)}
            )
            await self.idempotency_repo.create(idempotency_record)

            # 6. Audit Log
            audit_log = AuditLog(
                actor_id=user.id,
                entity_type="wallet",
                entity_id=str(wallet_id),
                action="deposit",
                metadata_json={
                    "amount": str(deposit_in.amount),
                    "reference": transaction_ref
                }
            )
            self.session.add(audit_log)

            # 7. Commit
            await self.session.commit()
            await self.session.refresh(wallet)
            
            logger.info("deposit_completed", reference=transaction_ref, wallet_id=str(wallet_id), amount=str(deposit_in.amount))
            return wallet

        except Exception as e:
            await self.session.rollback()
            if isinstance(e, HTTPException):
                raise e
            logger.exception("deposit_failed", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error during deposit")

    def _generate_request_hash(self, request: WalletDeposit) -> str:
        data = request.model_dump()
        data.pop("idempotency_key")
        dump = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(dump.encode()).hexdigest()
