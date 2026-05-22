from fastapi import APIRouter, Depends, Query
from src.api.schemas.transaction import TransactionHistoryResponse
from src.services.transfer import TransferService
from src.api.deps import DBDep, CurrentUser

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.get("/history", response_model=TransactionHistoryResponse)
async def get_history(
    db: DBDep, 
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    transfer_service = TransferService(db)
    items, total = await transfer_service.get_transaction_history(user.id, page=page, size=size)
    return TransactionHistoryResponse(
        items=items,
        total=total,
        page=page,
        size=size
    )
