import uuid
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from src.db.models import TransactionStatus

class TransferRequest(BaseModel):
    destination_wallet_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    idempotency_key: str = Field(..., min_length=1, max_length=100)

class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    transaction_reference: str
    source_wallet_id: Optional[uuid.UUID]
    destination_wallet_id: Optional[uuid.UUID]
    amount: Decimal
    currency: str
    status: TransactionStatus
    failure_reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

class TransactionHistoryResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    size: int
