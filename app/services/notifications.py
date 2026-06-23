"""Notification helper. Callers commit the surrounding transaction."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification


async def notify(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str | None = None,
) -> Notification:
    note = Notification(user_id=user_id, title=title, message=message)
    db.add(note)
    return note
