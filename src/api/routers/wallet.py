import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from src.api.schemas.wallet import WalletCreate, WalletResponse, WalletBalance, WalletDeposit
from src.api.schemas.transaction import TransferRequest, TransactionResponse, TransactionHistoryResponse
from src.services.wallet import WalletService
from src.services.transfer import TransferService
from src.api.deps import DBDep, CurrentUser

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.post("/create", response_model=WalletResponse, status_code=status.HTTP_201_CREATED, summary="Create a new wallet", description="Creates a new currency wallet for the authenticated user. The 'id' in the response is the Wallet ID needed for transfers.")
async def create_wallet(wallet_in: WalletCreate, db: DBDep, user: CurrentUser):
    wallet_service = WalletService(db)
    return await wallet_service.create_wallet(user, wallet_in)

@router.get("/list", response_model=List[WalletResponse], summary="List all my wallets", description="Returns a list of all wallets owned by the authenticated user. Use the 'id' field for transfer/deposit operations.")
async def list_wallets(db: DBDep, user: CurrentUser):
    wallet_service = WalletService(db)
    return await wallet_service.get_user_wallets(user.id)

@router.get("/{wallet_id}/balance", response_model=WalletBalance, summary="Get wallet balance")
async def get_balance(wallet_id: uuid.UUID, db: DBDep, user: CurrentUser):
    wallet_service = WalletService(db)
    wallet = await wallet_service.get_wallet(wallet_id, user.id)
    return WalletBalance(balance=wallet.balance, currency=wallet.currency)

@router.post("/{wallet_id}/deposit", response_model=WalletResponse, summary="Deposit funds", description="Add funds to a specific wallet. This is used for testing and simulated top-ups.")
async def deposit_funds(wallet_id: uuid.UUID, deposit_in: WalletDeposit, db: DBDep, user: CurrentUser):
    wallet_service = WalletService(db)
    return await wallet_service.deposit(wallet_id, user.id, deposit_in.amount)

@router.post("/{wallet_id}/transfer", response_model=TransactionResponse, summary="Transfer money", description="Transfer funds from your wallet to another wallet. Requires a unique 'idempotency_key' to prevent duplicate transfers.")
async def transfer_money(wallet_id: uuid.UUID, transfer_in: TransferRequest, db: DBDep, user: CurrentUser):
    transfer_service = TransferService(db)
    return await transfer_service.transfer(user, wallet_id, transfer_in)
