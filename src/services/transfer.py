import uuid
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Transaction, TransactionStatus, IdempotencyRecord, AuditLog, User
from src.repositories.wallet import WalletRepository
from src.repositories.transaction import TransactionRepository, IdempotencyRepository
from src.api.schemas.transaction import TransferRequest
import structlog

logger = structlog.get_logger(__name__)

class TransferService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.wallet_repo = WalletRepository(session)
        self.transaction_repo = TransactionRepository(session)
        self.idempotency_repo = IdempotencyRepository(session)

    async def transfer(self, user: User, source_wallet_id: uuid.UUID, transfer_in: TransferRequest) -> Transaction:
        # 1. Idempotency Check
        request_hash = self._generate_request_hash(transfer_in)
        existing_idempotency = await self.idempotency_repo.get_by_key(transfer_in.idempotency_key, user.id)
        
        if existing_idempotency:
            if existing_idempotency.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Idempotency key reused with different request parameters"
                )
            logger.info("idempotency_hit", key=transfer_in.idempotency_key)
            # In a real system, we'd return the stored response. 
            # For this simple example, we might just throw or return the transaction.
            # Let's try to find the transaction associated with this idempotency key.
            # Assuming idempotency_key is unique in transactions table too.
            from sqlalchemy import select
            query = select(Transaction).where(Transaction.idempotency_key == transfer_in.idempotency_key)
            result = await self.session.execute(query)
            transaction = result.scalar_one_or_none()
            if transaction:
                return transaction
            else:
                # Idempotency record exists but transaction doesn't? Should not happen in atomic tx.
                # Return the stored body if we had one.
                raise HTTPException(status_code=existing_idempotency.response_code, detail="Already processed")

        # 2. Begin Transfer Process
        transaction_ref = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        
        # We wrap everything in a try-except to handle failures and record them
        try:
            # Sort IDs to prevent deadlocks
            wallet_ids = [source_wallet_id, transfer_in.destination_wallet_id]
            if source_wallet_id == transfer_in.destination_wallet_id:
                raise HTTPException(status_code=400, detail="Source and destination wallets must be different")

            # 3. Lock Wallets (Pessimistic Locking)
            wallets = await self.wallet_repo.get_multiple_for_update(wallet_ids)
            
            if len(wallets) < 2:
                raise HTTPException(status_code=404, detail="One or both wallets not found")
            
            # Identify source and destination from the locked list
            source_wallet = next(w for w in wallets if w.id == source_wallet_id)
            dest_wallet = next(w for w in wallets if w.id == transfer_in.destination_wallet_id)
            
            # 4. Validations
            if source_wallet.user_id != user.id:
                raise HTTPException(status_code=403, detail="Not authorized to transfer from this wallet")
            
            if source_wallet.currency != dest_wallet.currency:
                # Real systems might support FX, but we'll keep it simple for now
                raise HTTPException(status_code=400, detail="Cross-currency transfers not supported")
            
            if source_wallet.balance < transfer_in.amount:
                raise HTTPException(status_code=400, detail="Insufficient balance")

            # 5. Execute Atomic Update
            source_wallet.balance -= transfer_in.amount
            dest_wallet.balance += transfer_in.amount
            
            # 6. Create Transaction Record
            transaction = Transaction(
                transaction_reference=transaction_ref,
                source_wallet_id=source_wallet_id,
                destination_wallet_id=transfer_in.destination_wallet_id,
                amount=transfer_in.amount,
                currency=source_wallet.currency,
                status=TransactionStatus.COMPLETED,
                idempotency_key=transfer_in.idempotency_key,
                completed_at=datetime.now(timezone.utc)
            )
            await self.transaction_repo.create(transaction)
            
            # 7. Create Idempotency Record (within same transaction)
            idempotency_record = IdempotencyRecord(
                idempotency_key=transfer_in.idempotency_key,
                user_id=user.id,
                request_hash=request_hash,
                response_code=200,
                response_body={"transaction_id": str(transaction.id), "status": "COMPLETED"}
            )
            await self.idempotency_repo.create(idempotency_record)
            
            # 8. Audit Log
            audit_log = AuditLog(
                actor_id=user.id,
                entity_type="wallet",
                entity_id=str(source_wallet_id),
                action="transfer",
                metadata_json={
                    "amount": str(transfer_in.amount),
                    "destination": str(transfer_in.destination_wallet_id),
                    "reference": transaction_ref
                }
            )
            self.session.add(audit_log)
            
            # 9. Commit
            await self.session.commit()
            await self.session.refresh(transaction)
            
            logger.info("transfer_completed", reference=transaction_ref, amount=str(transfer_in.amount))
            return transaction

        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.exception("transfer_failed", error=str(e))
            # Optional: Record failed transaction in DB if needed (would require a separate transaction)
            raise HTTPException(status_code=500, detail="Internal server error during transfer")

    def _generate_request_hash(self, request: TransferRequest) -> str:
        data = request.model_dump()
        # Exclude idempotency_key from hash itself as it's the lookup key
        data.pop("idempotency_key")
        dump = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(dump.encode()).hexdigest()

    async def get_transaction_history(self, user_id: uuid.UUID, page: int = 1, size: int = 20):
        wallets = await self.wallet_repo.get_user_wallets(user_id)
        wallet_ids = [w.id for w in wallets]
        if not wallet_ids:
            return [], 0
        
        skip = (page - 1) * size
        return await self.transaction_repo.get_history(wallet_ids, skip=skip, limit=size)
