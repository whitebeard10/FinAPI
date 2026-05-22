import asyncio
import pytest
import uuid
from httpx import AsyncClient
from decimal import Decimal

async def get_auth_header(client: AsyncClient, email: str):
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"}
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_create_wallet_and_transfer(client: AsyncClient, db_session):
    headers = await get_auth_header(client, "user1@example.com")
    
    # Create source wallet
    res1 = await client.post("/api/v1/wallet/create", json={"currency": "USD"}, headers=headers)
    assert res1.status_code == 201
    source_wallet_id = res1.json()["id"]
    
    # Manually add balance for testing (since we don't have a deposit API yet)
    from src.db.models import Wallet
    from sqlalchemy import update
    await db_session.execute(
        update(Wallet).where(Wallet.id == uuid.UUID(source_wallet_id)).values(balance=1000.0)
    )
    await db_session.commit()

    # Create destination wallet (another user)
    headers2 = await get_auth_header(client, "user2@example.com")
    res2 = await client.post("/api/v1/wallet/create", json={"currency": "USD"}, headers=headers2)
    dest_wallet_id = res2.json()["id"]

    # Execute transfer
    idempotency_key = str(uuid.uuid4())
    transfer_res = await client.post(
        f"/api/v1/wallet/{source_wallet_id}/transfer",
        json={
            "destination_wallet_id": dest_wallet_id,
            "amount": 100.0,
            "idempotency_key": idempotency_key
        },
        headers=headers
    )
    assert transfer_res.status_code == 200
    
    # Verify balances
    balance_res = await client.get(f"/api/v1/wallet/{source_wallet_id}/balance", headers=headers)
    assert float(balance_res.json()["balance"]) == 900.0
    
    balance_res2 = await client.get(f"/api/v1/wallet/{dest_wallet_id}/balance", headers=headers2)
    assert float(balance_res2.json()["balance"]) == 100.0

@pytest.mark.asyncio
async def test_transfer_idempotency(client: AsyncClient, db_session):
    headers = await get_auth_header(client, "idem@example.com")
    res1 = await client.post("/api/v1/wallet/create", json={"currency": "USD"}, headers=headers)
    source_id = res1.json()["id"]
    
    from src.db.models import Wallet
    from sqlalchemy import update
    await db_session.execute(update(Wallet).where(Wallet.id == uuid.UUID(source_id)).values(balance=1000.0))
    await db_session.commit()

    headers2 = await get_auth_header(client, "idem2@example.com")
    res2 = await client.post("/api/v1/wallet/create", json={"currency": "USD"}, headers=headers2)
    dest_id = res2.json()["id"]

    idempotency_key = "test-idem-key"
    payload = {
        "destination_wallet_id": dest_id,
        "amount": 100.0,
        "idempotency_key": idempotency_key
    }

    # First request
    res = await client.post(f"/api/v1/wallet/{source_id}/transfer", json=payload, headers=headers)
    assert res.status_code == 200
    txn_id = res.json()["id"]

    # Second request with same key
    res_retry = await client.post(f"/api/v1/wallet/{source_id}/transfer", json=payload, headers=headers)
    assert res_retry.status_code == 200
    assert res_retry.json()["id"] == txn_id
    
    # Verify balance only deducted once
    balance_res = await client.get(f"/api/v1/wallet/{source_id}/balance", headers=headers)
    assert float(balance_res.json()["balance"]) == 900.0

@pytest.mark.asyncio
async def test_concurrent_transfers(client: AsyncClient, db_session):
    """
    Simulate multiple concurrent transfers from the same wallet to verify row-level locking.
    Note: SQLite does not support FOR UPDATE locking for concurrency in the same way Postgres does.
    This test is primarily intended for a Postgres environment.
    """
    if "sqlite" in str(db_session.bind.url):
        pytest.skip("Concurrency test with row-level locks requires PostgreSQL")
    
    headers = await get_auth_header(client, "concurrent@example.com")
    res1 = await client.post("/api/v1/wallet/create", json={"currency": "USD"}, headers=headers)
    source_id = res1.json()["id"]
    
    from src.db.models import Wallet
    from sqlalchemy import update
    await db_session.execute(update(Wallet).where(Wallet.id == uuid.UUID(source_id)).values(balance=1000.0))
    await db_session.commit()

    headers2 = await get_auth_header(client, "concurrent2@example.com")
    res2 = await client.post("/api/v1/wallet/create", json={"currency": "USD"}, headers=headers2)
    dest_id = res2.json()["id"]

    # Fire 5 concurrent requests of 100 each
    tasks = []
    for i in range(5):
        payload = {
            "destination_wallet_id": dest_id,
            "amount": 100.0,
            "idempotency_key": f"concurrent-key-{i}"
        }
        tasks.append(client.post(f"/api/v1/wallet/{source_id}/transfer", json=payload, headers=headers))
    
    responses = await asyncio.gather(*tasks)
    
    for r in responses:
        assert r.status_code == 200
    
    # Verify final balance is 500.0
    balance_res = await client.get(f"/api/v1/wallet/{source_id}/balance", headers=headers)
    assert float(balance_res.json()["balance"]) == 500.0
