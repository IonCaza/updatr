from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

_sync_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
sync_engine = create_engine(_sync_url, echo=False, pool_pre_ping=True)
SyncSession = sessionmaker(sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
