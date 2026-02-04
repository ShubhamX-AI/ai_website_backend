from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from src.core.config import settings
from typing import AsyncGenerator

# Create async engine with pooling
# postgresql+psycopg automatically uses async if used with create_async_engine
engine = create_async_engine(
    settings.DATABASE_URL,
    # Pool size: Number of permanent connections to keep
    pool_size=10,
    # Max overflow: Number of temporary connections allowed beyond pool_size
    max_overflow=20,
    # Pool timeout: Seconds to wait for a connection from the pool
    pool_timeout=30,
    # Pool recycle: Seconds after which a connection is closed and replaced
    pool_recycle=1800,
    # Pool pre-ping: Verify connection health before using
    pool_pre_ping=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency for FastAPI to get a database session.
    """
    async with AsyncSessionLocal() as session:
        yield session
