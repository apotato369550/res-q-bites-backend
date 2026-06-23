"""Test fixtures: isolated temp SQLite DB + ASGI client.

DB_URL is set to a throwaway temp file *before* importing the app so the engine
binds to it. Tables are recreated fresh for every test.
"""
import os
import tempfile

import pytest_asyncio

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DB_URL"] = "sqlite+aiosqlite:///" + _db_path.replace("\\", "/")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
