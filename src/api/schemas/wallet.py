import uuid
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class WalletCreate(BaseModel):
    currency: str = Field(default="USD", max_length=10)

class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    user_id: uuid.UUID
    balance: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime

class WalletBalance(BaseModel):
    balance: Decimal
    currency: str

class WalletDeposit(BaseModel):
    amount: Decimal = Field(..., gt=0)
    idempotency_key: str = Field(..., min_length=1, max_length=100)
