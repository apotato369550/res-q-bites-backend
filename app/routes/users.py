"""Profile management (all roles) — CSV #3."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Re-load with the establishment profile eagerly attached.
    user = await db.get(
        User,
        current_user.id,
        options=[selectinload(User.establishment_profile)],
        populate_existing=True,
    )
    return user


@router.put("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(current_user, field, value)
    await db.commit()
    user = await db.get(
        User,
        current_user.id,
        options=[selectinload(User.establishment_profile)],
        populate_existing=True,
    )
    return user
