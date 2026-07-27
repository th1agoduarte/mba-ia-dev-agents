
from db.engine import close_db, engine, Base, init_db
from asyncio import run

async def reset_db() -> None:
    # Apaga todas as tabelas do banco de dados e recria-as (idempotente).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await init_db()
    await close_db()

if __name__ == "__main__":
    run(reset_db())