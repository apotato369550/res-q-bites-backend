"""Donation audit-trail helper.

Keeps DonationHistory writes out of the route handlers. Callers are responsible
for committing the surrounding transaction.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DonationHistory


async def record(
    db: AsyncSession,
    donation_id: int,
    action: str,
    actor_id: int | None = None,
    notes: str | None = None,
) -> DonationHistory:
    entry = DonationHistory(
        donation_id=donation_id,
        action=action,
        actor_id=actor_id,
        notes=notes,
    )
    db.add(entry)
    return entry
