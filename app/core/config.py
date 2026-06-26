"""Application configuration.

Plain ``os.getenv`` over ``python-dotenv`` — no validation layer (mirrors the
reference architecture, minus the AI/LLM settings).
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Database --------------------------------------------------------------------
# SQLite single-file DB via the async aiosqlite driver. No server required.
DB_URL: str = os.getenv("DB_URL", "sqlite+aiosqlite:///./resqbites.db")

# Auth ------------------------------------------------------------------------
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-to-a-long-random-string")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))

# Seed admin (consumed by scripts/utils/seed.py) ------------------------------
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@resqbites.org")
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin12345")
