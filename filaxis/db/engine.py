from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from filaxis.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    from filaxis.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
