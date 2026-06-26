"""Role-specific onboarding (CSV: separate flows per the conversation)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.db.models import EstablishmentProfile, User, UserRole
from app.db.session import get_db
from app.schemas.auth import EstablishmentOnboarding, IndividualOnboarding
from app.schemas.user import UserOut

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/individual", response_model=UserOut)
async def onboard_individual(
    payload: IndividualOnboarding,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.individual:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not an individual account")
    current_user.first_name = payload.first_name
    current_user.last_name = payload.last_name
    if payload.phone is not None:
        current_user.phone = payload.phone
    await db.commit()
    return await db.get(
        User,
        current_user.id,
        options=[selectinload(User.establishment_profile)],
        populate_existing=True,
    )


@router.post("/establishment", response_model=UserOut)
async def onboard_establishment(
    payload: EstablishmentOnboarding,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.establishment:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not an establishment account")

    existing = (
        await db.execute(
            select(EstablishmentProfile).where(
                EstablishmentProfile.user_id == current_user.id
            )
        )
    ).scalars().first()

    if existing:
        existing.establishment_name = payload.establishment_name
        existing.establishment_type = payload.establishment_type
        existing.address = payload.address
    else:
        db.add(
            EstablishmentProfile(
                user_id=current_user.id,
                establishment_name=payload.establishment_name,
                establishment_type=payload.establishment_type,
                address=payload.address,
            )
        )
    if payload.phone is not None:
        current_user.phone = payload.phone

    await db.commit()
    return await db.get(
        User,
        current_user.id,
        options=[selectinload(User.establishment_profile)],
        populate_existing=True,
    )
