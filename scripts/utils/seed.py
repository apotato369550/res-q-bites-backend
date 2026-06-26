"""Seed baseline data: admin, demo LGU + LGU account, badges, reward rule.

Idempotent-ish: skips rows that already exist by a natural key.

Usage (from project root):
    python scripts/utils/seed.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import select  # noqa: E402

from app.core.config import ADMIN_EMAIL, ADMIN_PASSWORD  # noqa: E402
from app.db.models import (  # noqa: E402
    LGU,
    Badge,
    Base,
    RewardRule,
    User,
    UserRole,
)
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.services.security import hash_password  # noqa: E402

# A few Cebu City LGU food banks (approx coordinates) for nearby search demos.
LGUS = [
    {"name": "Barangay Lahug Food Bank", "barangay": "Lahug",
     "address": "Lahug, Cebu City", "latitude": 10.3340, "longitude": 123.9000},
    {"name": "Barangay Guadalupe Food Bank", "barangay": "Guadalupe",
     "address": "Guadalupe, Cebu City", "latitude": 10.3260, "longitude": 123.8870},
    {"name": "Barangay Mabolo Food Bank", "barangay": "Mabolo",
     "address": "Mabolo, Cebu City", "latitude": 10.3170, "longitude": 123.9120},
]

BADGES = [
    {"code": "first_bite", "name": "First Bite", "threshold_points": 10,
     "description": "Completed your first donation."},
    {"code": "helping_hand", "name": "Helping Hand", "threshold_points": 50,
     "description": "Reached 50 points."},
    {"code": "hunger_hero", "name": "Hunger Hero", "threshold_points": 100,
     "description": "Reached 100 points."},
    {"code": "community_champion", "name": "Community Champion", "threshold_points": 250,
     "description": "Reached 250 points."},
]


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Admin
        admin = (
            await db.execute(select(User).where(User.email == ADMIN_EMAIL.lower()))
        ).scalars().first()
        if admin is None:
            db.add(
                User(
                    email=ADMIN_EMAIL.lower(),
                    password_hash=hash_password(ADMIN_PASSWORD),
                    role=UserRole.admin,
                    first_name="System",
                    last_name="Admin",
                )
            )
            print(f"Seeded admin: {ADMIN_EMAIL}")

        # LGUs (verified so they show up in nearby search)
        lgu_records = []
        for spec in LGUS:
            existing = (
                await db.execute(select(LGU).where(LGU.name == spec["name"]))
            ).scalars().first()
            if existing is None:
                lgu = LGU(verified=True, **spec)
                db.add(lgu)
                lgu_records.append(lgu)
            else:
                lgu_records.append(existing)
        await db.flush()

        # Demo LGU account linked to the first LGU
        demo_lgu_email = "lgu.lahug@resqbites.org"
        demo_lgu = (
            await db.execute(select(User).where(User.email == demo_lgu_email))
        ).scalars().first()
        if demo_lgu is None and lgu_records:
            db.add(
                User(
                    email=demo_lgu_email,
                    password_hash=hash_password("lgu12345"),
                    role=UserRole.lgu,
                    first_name="Lahug",
                    last_name="LGU",
                    managing_lgu_id=lgu_records[0].id,
                )
            )
            print(f"Seeded LGU account: {demo_lgu_email} (password: lgu12345)")

        # Badges
        for spec in BADGES:
            existing = (
                await db.execute(select(Badge).where(Badge.code == spec["code"]))
            ).scalars().first()
            if existing is None:
                db.add(Badge(**spec))

        # Default active reward rule
        rule = (
            await db.execute(select(RewardRule).where(RewardRule.active.is_(True)))
        ).scalars().first()
        if rule is None:
            db.add(RewardRule(name="Default", points_per_donation=10, active=True))
            print("Seeded default reward rule (10 pts/donation).")

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
