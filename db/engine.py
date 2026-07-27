import os
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from .models import Base

CURRENT_PATH = __file__.rsplit("/", 1)[0]
BASE_PATH = f"{CURRENT_PATH}/../agents"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///" + f"{BASE_PATH}/tickets.db",
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def init_db() -> None:
    """Cria as tabelas se não existirem (idempotente)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Fecha o pool de conexões — chamado no shutdown."""
    await engine.dispose()
