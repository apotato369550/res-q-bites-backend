"""Donor-facing donation endpoints — CSV #6, #7, #8, #9, #12."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_donor
from app.db.models import (
    Donation,
    DonationMethod,
    DonationStatus,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.common import Message
from app.schemas.donation import (
    DonationCreate,
    DonationHistoryOut,
    DonationOut,
    DonationSummary,
    DonationUpdate,
)
from app.services import history

router = APIRouter(tags=["donations"])


def _validate_method(role: UserRole, payload_method: DonationMethod, pickup_location):
    """Individuals must drop off; establishments may pick up or drop off."""
    if role == UserRole.individual and payload_method != DonationMethod.dropoff:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Individuals must drop off donations (donation_method=dropoff)",
        )
    if payload_method == DonationMethod.pickup and not pickup_location:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "pickup_location is required when donation_method=pickup",
        )


async def _get_owned_donation(db: AsyncSession, donation_id: int, user: User) -> Donation:
    donation = await db.get(Donation, donation_id)
    if donation is None or donation.donor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donation not found")
    return donation


@router.post("/donations", response_model=DonationOut, status_code=status.HTTP_201_CREATED)
async def create_donation(
    payload: DonationCreate,
    current_user: User = Depends(require_donor),
    db: AsyncSession = Depends(get_db),
):
    _validate_method(current_user.role, payload.donation_method, payload.pickup_location)

    pickup = payload.pickup_location
    if current_user.role == UserRole.individual:
        pickup = None  # enforced: individuals only drop off

    donation = Donation(
        donor_id=current_user.id,
        lgu_id=payload.lgu_id,
        title=payload.title,
        description=payload.description,
        quantity=payload.quantity,
        food_category=payload.food_category,
        quote=payload.quote,
        photo_base64=payload.photo_base64,
        pickup_location=pickup,
        dropoff_location=payload.dropoff_location,
        donation_method=payload.donation_method,
        status=DonationStatus.pending,
    )
    db.add(donation)
    await db.flush()
    await history.record(db, donation.id, "created", actor_id=current_user.id)
    await db.commit()
    await db.refresh(donation)
    return donation


@router.get("/donations/my", response_model=list[DonationSummary])
async def my_donations(
    status_filter: DonationStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_donor),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Donation).where(Donation.donor_id == current_user.id)
    if status_filter is not None:
        stmt = stmt.where(Donation.status == status_filter)
    stmt = stmt.order_by(Donation.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


@router.get("/donations/history", response_model=list[DonationSummary])
async def donation_history_list(
    current_user: User = Depends(require_donor),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Donation)
        .where(
            Donation.donor_id == current_user.id,
            Donation.status == DonationStatus.completed,
        )
        .order_by(Donation.updated_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.get("/donations/{donation_id}", response_model=DonationOut)
async def get_donation(
    donation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    donation = await db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donation not found")
    # Donor sees own; LGU/admin can see any.
    if (
        current_user.role in (UserRole.individual, UserRole.establishment)
        and donation.donor_id != current_user.id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donation not found")
    return donation


@router.get("/donations/{donation_id}/history", response_model=list[DonationHistoryOut])
async def get_donation_history(
    donation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    donation = await db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donation not found")
    if (
        current_user.role in (UserRole.individual, UserRole.establishment)
        and donation.donor_id != current_user.id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donation not found")
    await db.refresh(donation, attribute_names=["history"])
    return donation.history


@router.put("/donations/{donation_id}", response_model=DonationOut)
async def update_donation(
    donation_id: int,
    payload: DonationUpdate,
    current_user: User = Depends(require_donor),
    db: AsyncSession = Depends(get_db),
):
    donation = await _get_owned_donation(db, donation_id, current_user)
    if donation.status != DonationStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only pending donations can be edited"
        )
    data = payload.model_dump(exclude_unset=True)
    new_method = data.get("donation_method", donation.donation_method)
    new_pickup = data.get("pickup_location", donation.pickup_location)
    _validate_method(current_user.role, new_method, new_pickup)
    for field, value in data.items():
        setattr(donation, field, value)
    await history.record(db, donation.id, "updated", actor_id=current_user.id)
    await db.commit()
    await db.refresh(donation)
    return donation


@router.delete("/donations/{donation_id}", response_model=Message)
async def cancel_donation(
    donation_id: int,
    current_user: User = Depends(require_donor),
    db: AsyncSession = Depends(get_db),
):
    donation = await _get_owned_donation(db, donation_id, current_user)
    if donation.status not in (DonationStatus.pending, DonationStatus.accepted):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only pending or accepted donations can be cancelled",
        )
    donation.status = DonationStatus.cancelled
    await history.record(db, donation.id, "cancelled", actor_id=current_user.id)
    await db.commit()
    return Message(detail="donation cancelled")
