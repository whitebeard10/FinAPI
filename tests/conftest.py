import asyncio
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from src.db.base import Base
from src.main import app
from src.api.deps import get_db
from httpx import AsyncClient
import os
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    mock_limiter = AsyncMock()
    mock_limiter.is_rate_limited.return_value = False
    monkeypatch.setattr("src.core.rate_limit.get_rate_limiter", lambda: mock_limiter)
    return mock_limiter

# Use the same Postgres server but a different database name for isolation
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "localhost")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
# We use a suffix to ensure tests don't touch the production data
BASE_DB = os.getenv("POSTGRES_DB", "finapi")
TEST_DB = f"{BASE_DB}_test"

if os.getenv("POSTGRES_SERVER"):
    # URL for connecting to 'postgres' db to create the test db
    ADMIN_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}/postgres"
    TEST_DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}/{TEST_DB}"
else:
    TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)

async def create_test_db():
    """Create the test database if it doesn't exist."""
    if not os.getenv("POSTGRES_SERVER"):
        return
    
    admin_engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        # Check if exists
        result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{TEST_DB}'"))
        if not result.scalar():
            await conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    await admin_engine.dispose()

@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    await create_test_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # We do NOT drop all here anymore to prevent race conditions with the app
    # and to allow manual inspection if a test fails.
    # The drop_all at the START of the next run ensures a clean slate.

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
