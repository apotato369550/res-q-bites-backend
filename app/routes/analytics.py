"""LGU barangay analytics & reports — CSV #20, #21."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_lgu
from app.db.models import (
    Beneficiary,
    Distribution,
    Donation,
    DonationStatus,
    FoodCategory,
    InventoryItem,
    InventoryStatus,
    User,
)
from app.db.session import get_db

router = APIRouter(prefix="/lgu", tags=["lgu-analytics"])


def _lgu_id(user: User) -> int:
    if user.managing_lgu_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "LGU account not linked to an LGU")
    return user.managing_lgu_id


@router.get("/analytics")
async def analytics(
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _lgu_id(current_user)

    by_status = dict(
        (
            await db.execute(
                select(Donation.status, func.count())
                .where(Donation.lgu_id == lgu_id)
                .group_by(Donation.status)
            )
        ).all()
    )
    by_category = dict(
        (
            await db.execute(
                select(Donation.food_category, func.count())
                .where(Donation.lgu_id == lgu_id)
                .group_by(Donation.food_category)
            )
        ).all()
    )
    return {
        "donations_by_status": {s.value: c for s, c in by_status.items()},
        "donations_by_category": {c.value: n for c, n in by_category.items()},
        "in_stock_items": (
            await db.execute(
                select(func.count()).select_from(InventoryItem).where(
                    InventoryItem.lgu_id == lgu_id,
                    InventoryItem.status == InventoryStatus.in_stock,
                )
            )
        ).scalar_one(),
        "total_distributions": (
            await db.execute(
                select(func.count()).select_from(Distribution).where(
                    Distribution.lgu_id == lgu_id
                )
            )
        ).scalar_one(),
        "total_beneficiaries": (
            await db.execute(
                select(func.count()).select_from(Beneficiary).where(
                    Beneficiary.lgu_id == lgu_id
                )
            )
        ).scalar_one(),
    }


@router.get("/reports")
async def reports(
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    """A flat report summary the client can render or export."""
    lgu_id = _lgu_id(current_user)
    completed = (
        await db.execute(
            select(func.count()).select_from(Donation).where(
                Donation.lgu_id == lgu_id,
                Donation.status == DonationStatus.completed,
            )
        )
    ).scalar_one()
    categories = {c.value: 0 for c in FoodCategory}
    rows = (
        await db.execute(
            select(Donation.food_category, func.count())
            .where(
                Donation.lgu_id == lgu_id,
                Donation.status == DonationStatus.completed,
            )
            .group_by(Donation.food_category)
        )
    ).all()
    for cat, count in rows:
        categories[cat.value] = count
    return {
        "lgu_id": lgu_id,
        "completed_donations": completed,
        "completed_by_category": categories,
    }
