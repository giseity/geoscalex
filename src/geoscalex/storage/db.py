from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from geoscalex.config import settings
from geoscalex.storage.models import Base


def database_url() -> str:
    return f"sqlite+aiosqlite:///{settings.database_path}"


engine = create_async_engine(database_url())
Session = async_sessionmaker(engine, expire_on_commit=False)


async def init_database() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with Session() as session:
        yield session
