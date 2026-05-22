import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from src.api.schemas.wallet import WalletCreate, WalletResponse, WalletBalance
from src.api.schemas.transaction import TransferRequest, TransactionResponse, TransactionHistoryResponse
from src.services.wallet import WalletService
from src.services.transfer import TransferService
from src.api.deps import DBDep, CurrentUser

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.post("/create", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def create_wallet(wallet_in: WalletCreate, db: DBDep, user: CurrentUser):
    wallet_service = WalletService(db)
    return await wallet_service.create_wallet(user, wallet_in)

@router.get("/list", response_model=List[WalletResponse])
async def list_wallets(db: DBDep, user: CurrentUser):
    wallet_service = WalletService(db)
    return await wallet_service.get_user_wallets(user.id)

@router.get("/{wallet_id}/balance", response_model=WalletBalance)
async def get_balance(wallet_id: uuid.UUID, db: DBDep, user: CurrentUser):
    wallet_service = WalletService(db)
    wallet = await wallet_service.get_wallet(wallet_id, user.id)
    return WalletBalance(balance=wallet.balance, currency=wallet.currency)

@router.post("/{wallet_id}/transfer", response_model=TransactionResponse)
async def transfer_money(wallet_id: uuid.UUID, transfer_in: TransferRequest, db: DBDep, user: CurrentUser):
    transfer_service = TransferService(db)
    return await transfer_service.transfer(user, wallet_id, transfer_in)
