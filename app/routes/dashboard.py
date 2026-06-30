"""Role-aware dashboard summary cards — CSV #4."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import (
    Beneficiary,
    Distribution,
    Donation,
    DonationStatus,
    InventoryItem,
    InventoryStatus,
    LGU,
    User,
    UserRole,
)
from app.db.session import get_db

router = APIRouter(tags=["dashboard"])


async def _count(db: AsyncSession, stmt) -> int:
    return (await db.execute(stmt)).scalar_one()


@router.get("/dashboard")
async def dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current_user.role

    if role in (UserRole.individual, UserRole.establishment):
        base = select(func.count()).select_from(Donation).where(
            Donation.donor_id == current_user.id
        )
        total = await _count(db, base)
        completed = await _count(
            db, base.where(Donation.status == DonationStatus.completed)
        )
        active = await _count(
            db,
            base.where(
                Donation.status.in_(
                    [DonationStatus.pending, DonationStatus.accepted, DonationStatus.scheduled]
                )
            ),
        )
        return {
            "role": role.value,
            "total_donations": total,
            "completed_donations": completed,
            "active_donations": active,
        }

    if role == UserRole.lgu:
        lgu_id = current_user.managing_lgu_id
        d = select(func.count()).select_from(Donation).where(Donation.lgu_id == lgu_id)
        pending = await _count(
            db,
            select(func.count()).select_from(Donation).where(
                Donation.status == DonationStatus.pending,
                (Donation.lgu_id == lgu_id) | (Donation.lgu_id.is_(None)),
            ),
        )
        return {
            "role": role.value,
            "pending_donations": pending,
            "accepted_donations": await _count(
                db, d.where(Donation.status == DonationStatus.accepted)
            ),
            "completed_donations": await _count(
                db, d.where(Donation.status == DonationStatus.completed)
            ),
            "in_stock_items": await _count(
                db,
                select(func.count()).select_from(InventoryItem).where(
                    InventoryItem.lgu_id == lgu_id,
                    InventoryItem.status == InventoryStatus.in_stock,
                ),
            ),
            "beneficiaries": await _count(
                db,
                select(func.count()).select_from(Beneficiary).where(
                    Beneficiary.lgu_id == lgu_id
                ),
            ),
            "distributions": await _count(
                db,
                select(func.count()).select_from(Distribution).where(
                    Distribution.lgu_id == lgu_id
                ),
            ),
        }

    # admin
    return {
        "role": role.value,
        "total_users": await _count(db, select(func.count()).select_from(User)),
        "total_lgus": await _count(db, select(func.count()).select_from(LGU)),
        "total_donations": await _count(db, select(func.count()).select_from(Donation)),
        "completed_donations": await _count(
            db,
            select(func.count()).select_from(Donation).where(
                Donation.status == DonationStatus.completed
            ),
        ),
    }
