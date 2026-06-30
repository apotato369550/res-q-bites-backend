"""LGU-facing endpoints: donation queue management (Phase 1) and
inventory / beneficiaries / distribution (Phase 2). CSV #13-#19."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_lgu
from app.db.models import (
    Beneficiary,
    Distribution,
    Donation,
    DonationStatus,
    FoodSafetyStatus,
    InventoryItem,
    InventoryStatus,
    User,
)
from app.db.session import get_db
from app.schemas.common import Message
from app.schemas.donation import (
    ActionNote,
    DonationOut,
    DonationSummary,
    ScheduleRequest,
)
from app.schemas.lgu_ops import (
    BeneficiaryCreate,
    BeneficiaryOut,
    BeneficiaryUpdate,
    DistributionCreate,
    DistributionOut,
    FoodSafetyRequest,
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemUpdate,
)
from app.services import history
from app.services.notifications import notify

router = APIRouter(prefix="/lgu", tags=["lgu"])


def _require_lgu_id(user: User) -> int:
    if user.managing_lgu_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This LGU account is not linked to an LGU record (set managing_lgu_id)",
        )
    return user.managing_lgu_id


async def _load_queue_donation(db: AsyncSession, donation_id: int, lgu_id: int) -> Donation:
    """Fetch a donation that this LGU may act on (assigned to it or still unassigned)."""
    donation = await db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donation not found")
    if donation.lgu_id not in (None, lgu_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Donation belongs to another LGU")
    return donation


# --- Donation queue (Phase 1) ------------------------------------------------
@router.get("/donations", response_model=list[DonationSummary])
async def queue(
    status_filter: DonationStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    stmt = select(Donation).where(Donation.lgu_id == lgu_id)
    if status_filter is not None:
        stmt = stmt.where(Donation.status == status_filter)
    stmt = stmt.order_by(Donation.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


@router.get("/donations/pending", response_model=list[DonationSummary])
async def pending(
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    """Unassigned pending donations + ones already directed at this LGU."""
    lgu_id = _require_lgu_id(current_user)
    stmt = (
        select(Donation)
        .where(
            Donation.status == DonationStatus.pending,
            (Donation.lgu_id == lgu_id) | (Donation.lgu_id.is_(None)),
        )
        .order_by(Donation.created_at.asc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/donations/{donation_id}/accept", response_model=DonationOut)
async def accept(
    donation_id: int,
    payload: ActionNote | None = None,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    donation = await _load_queue_donation(db, donation_id, lgu_id)
    if donation.status != DonationStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Donation is not pending")
    donation.status = DonationStatus.accepted
    donation.lgu_id = lgu_id
    await history.record(db, donation.id, "accepted", actor_id=current_user.id,
                         notes=payload.notes if payload else None)
    await notify(db, donation.donor_id, "Donation accepted",
                 f"Your donation '{donation.title}' was accepted.")
    await db.commit()
    await db.refresh(donation)
    return donation


@router.post("/donations/{donation_id}/reject", response_model=DonationOut)
async def reject(
    donation_id: int,
    payload: ActionNote | None = None,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    donation = await _load_queue_donation(db, donation_id, lgu_id)
    if donation.status != DonationStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Donation is not pending")
    donation.status = DonationStatus.rejected
    donation.lgu_id = lgu_id
    await history.record(db, donation.id, "rejected", actor_id=current_user.id,
                         notes=payload.notes if payload else None)
    await notify(db, donation.donor_id, "Donation rejected",
                 f"Your donation '{donation.title}' was rejected.")
    await db.commit()
    await db.refresh(donation)
    return donation


@router.post("/donations/{donation_id}/schedule", response_model=DonationOut)
async def schedule(
    donation_id: int,
    payload: ScheduleRequest,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    donation = await _load_queue_donation(db, donation_id, lgu_id)
    if donation.status != DonationStatus.accepted:
        raise HTTPException(status.HTTP_409_CONFLICT, "Donation must be accepted first")
    donation.status = DonationStatus.scheduled
    donation.scheduled_pickup_at = payload.scheduled_pickup_at
    await history.record(db, donation.id, "scheduled", actor_id=current_user.id,
                         notes=payload.notes)
    await notify(db, donation.donor_id, "Pickup scheduled",
                 f"Pickup for '{donation.title}' is scheduled.")
    await db.commit()
    await db.refresh(donation)
    return donation


@router.post("/donations/{donation_id}/complete", response_model=DonationOut)
async def complete(
    donation_id: int,
    payload: ActionNote | None = None,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    """Mark received/completed → create an inventory item, notify."""
    lgu_id = _require_lgu_id(current_user)
    donation = await _load_queue_donation(db, donation_id, lgu_id)
    if donation.status not in (DonationStatus.accepted, DonationStatus.scheduled):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Donation must be accepted or scheduled before completion",
        )
    donation.status = DonationStatus.completed

    # Pull the received food into the LGU's inventory.
    db.add(
        InventoryItem(
            lgu_id=lgu_id,
            donation_id=donation.id,
            food_category=donation.food_category,
            quantity=0,
            unit=donation.quantity,
            status=InventoryStatus.in_stock,
        )
    )
    await history.record(
        db, donation.id, "completed", actor_id=current_user.id,
        notes=payload.notes if payload else None,
    )
    await notify(
        db, donation.donor_id, "Donation completed",
        f"Thank you! '{donation.title}' was received.",
    )
    await db.commit()
    await db.refresh(donation)
    return donation


# --- Food safety (Phase 2) — CSV #16 -----------------------------------------
@router.post("/donations/{donation_id}/food-safety", response_model=Message)
async def validate_food_safety(
    donation_id: int,
    payload: FoodSafetyRequest,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    donation = await _load_queue_donation(db, donation_id, lgu_id)
    # Apply the result to any inventory items sourced from this donation.
    items = (
        await db.execute(
            select(InventoryItem).where(InventoryItem.donation_id == donation.id)
        )
    ).scalars().all()
    for item in items:
        item.food_safety_status = payload.result
        if payload.result == FoodSafetyStatus.failed:
            item.status = InventoryStatus.expired
    await history.record(
        db, donation.id, f"food_safety_{payload.result.value}",
        actor_id=current_user.id, notes=payload.notes,
    )
    await db.commit()
    return Message(detail=f"food safety recorded as {payload.result.value}")


# --- Inventory (Phase 2) — CSV #17 -------------------------------------------
@router.get("/inventory", response_model=list[InventoryItemOut])
async def list_inventory(
    status_filter: InventoryStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    stmt = select(InventoryItem).where(InventoryItem.lgu_id == lgu_id)
    if status_filter is not None:
        stmt = stmt.where(InventoryItem.status == status_filter)
    stmt = stmt.order_by(InventoryItem.received_at.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/inventory", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
async def create_inventory(
    payload: InventoryItemCreate,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    item = InventoryItem(lgu_id=lgu_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _get_inventory(db: AsyncSession, item_id: int, lgu_id: int) -> InventoryItem:
    item = await db.get(InventoryItem, item_id)
    if item is None or item.lgu_id != lgu_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory item not found")
    return item


@router.put("/inventory/{item_id}", response_model=InventoryItemOut)
async def update_inventory(
    item_id: int,
    payload: InventoryItemUpdate,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    item = await _get_inventory(db, item_id, lgu_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/inventory/{item_id}", response_model=Message)
async def delete_inventory(
    item_id: int,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    item = await _get_inventory(db, item_id, lgu_id)
    await db.delete(item)
    await db.commit()
    return Message(detail="inventory item deleted")


# --- Beneficiaries (Phase 2) — CSV #19 ---------------------------------------
@router.get("/beneficiaries", response_model=list[BeneficiaryOut])
async def list_beneficiaries(
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    stmt = select(Beneficiary).where(Beneficiary.lgu_id == lgu_id).order_by(Beneficiary.name)
    return (await db.execute(stmt)).scalars().all()


@router.post("/beneficiaries", response_model=BeneficiaryOut, status_code=status.HTTP_201_CREATED)
async def create_beneficiary(
    payload: BeneficiaryCreate,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    beneficiary = Beneficiary(lgu_id=lgu_id, **payload.model_dump())
    db.add(beneficiary)
    await db.commit()
    await db.refresh(beneficiary)
    return beneficiary


async def _get_beneficiary(db: AsyncSession, bid: int, lgu_id: int) -> Beneficiary:
    beneficiary = await db.get(Beneficiary, bid)
    if beneficiary is None or beneficiary.lgu_id != lgu_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Beneficiary not found")
    return beneficiary


@router.put("/beneficiaries/{bid}", response_model=BeneficiaryOut)
async def update_beneficiary(
    bid: int,
    payload: BeneficiaryUpdate,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    beneficiary = await _get_beneficiary(db, bid, lgu_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(beneficiary, field, value)
    await db.commit()
    await db.refresh(beneficiary)
    return beneficiary


@router.delete("/beneficiaries/{bid}", response_model=Message)
async def delete_beneficiary(
    bid: int,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    beneficiary = await _get_beneficiary(db, bid, lgu_id)
    await db.delete(beneficiary)
    await db.commit()
    return Message(detail="beneficiary deleted")


# --- Distribution (Phase 2) — CSV #18 ----------------------------------------
@router.get("/distributions", response_model=list[DistributionOut])
async def list_distributions(
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    stmt = (
        select(Distribution)
        .where(Distribution.lgu_id == lgu_id)
        .order_by(Distribution.distributed_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.get("/distributions/{dist_id}", response_model=DistributionOut)
async def get_distribution(
    dist_id: int,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    lgu_id = _require_lgu_id(current_user)
    dist = await db.get(Distribution, dist_id)
    if dist is None or dist.lgu_id != lgu_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Distribution not found")
    return dist


@router.post("/distributions", response_model=DistributionOut, status_code=status.HTTP_201_CREATED)
async def record_distribution(
    payload: DistributionCreate,
    current_user: User = Depends(require_lgu),
    db: AsyncSession = Depends(get_db),
):
    """Record a distribution and decrement the drawn inventory item."""
    lgu_id = _require_lgu_id(current_user)
    beneficiary = await _get_beneficiary(db, payload.beneficiary_id, lgu_id)
    item = await _get_inventory(db, payload.inventory_item_id, lgu_id)

    qty = Decimal(str(payload.quantity))
    if Decimal(str(item.quantity)) < qty:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Inventory item {item.id} has insufficient quantity",
        )
    item.quantity = float(Decimal(str(item.quantity)) - qty)
    if item.quantity <= 0:
        item.status = InventoryStatus.distributed

    dist = Distribution(
        lgu_id=lgu_id,
        beneficiary_id=beneficiary.id,
        inventory_item_id=item.id,
        recorded_by=current_user.id,
        quantity=payload.quantity,
        notes=payload.notes,
    )
    db.add(dist)
    await db.commit()
    await db.refresh(dist)
    return dist
