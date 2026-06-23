"""Async engine, session factory, and the get_db() dependency.

SQLite specifics vs. the MySQL reference:
- No pool sizing args (SQLite uses the default pool).
- A ``PRAGMA foreign_keys=ON`` listener so FK cascades actually fire.
"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DB_URL

engine = create_async_engine(DB_URL, pool_pre_ping=True, future=True)

# SQLite does not enforce foreign keys unless asked to, per-connection.
if DB_URL.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency yielding an async session."""
    async with AsyncSessionLocal() as session:
        yield session
