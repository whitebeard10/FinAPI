import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Transaction, IdempotencyRecord
from src.repositories.base import BaseRepository

class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession):
        super().__init__(Transaction, session)

    async def get_history(
        self, wallet_ids: List[uuid.UUID], skip: int = 0, limit: int = 20
    ) -> Tuple[List[Transaction], int]:
        query = select(Transaction).where(
            (Transaction.source_wallet_id.in_(wallet_ids)) | 
            (Transaction.destination_wallet_id.in_(wallet_ids))
        ).order_by(Transaction.created_at.desc())
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.execute(count_query)
        total_count = total.scalar_one()
        
        # Paginate
        paginated_query = query.offset(skip).limit(limit)
        result = await self.session.execute(paginated_query)
        return list(result.scalars().all()), total_count

class IdempotencyRepository(BaseRepository[IdempotencyRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(IdempotencyRecord, session)

    async def get_by_key(self, key: str, user_id: uuid.UUID) -> Optional[IdempotencyRecord]:
        query = select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == key,
            IdempotencyRecord.user_id == user_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
