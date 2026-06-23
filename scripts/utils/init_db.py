"""Create all tables (no migrations — re-run after model changes).

Usage (from project root):
    python scripts/utils/init_db.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db.models import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created.")


if __name__ == "__main__":
    asyncio.run(main())
