"""Admin surface — users, LGU accounts + verification, system-wide analytics."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.db.models import (
    LGU,
    Donation,
    DonationStatus,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.admin import (
    AdminUserOut,
    AdminUserUpdate,
    LGUCreate,
    LGUUpdate,
)
from app.schemas.donation import LGUOut

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Users -------------------------------------------------------------------
@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    role: UserRole | None = Query(default=None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


@router.get("/users/{user_id}", response_model=AdminUserOut)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.put("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None:
        try:
            user.role = UserRole(data["role"])
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid role")
    if "is_active" in data and data["is_active"] is not None:
        user.is_active = data["is_active"]
    await db.commit()
    await db.refresh(user)
    return user


# --- LGUs --------------------------------------------------------------------
@router.get("/lgus", response_model=list[LGUOut])
async def list_lgus(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return (await db.execute(select(LGU).order_by(LGU.name))).scalars().all()


@router.post("/lgus", response_model=LGUOut, status_code=status.HTTP_201_CREATED)
async def create_lgu(
    payload: LGUCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    lgu = LGU(**payload.model_dump())
    db.add(lgu)
    await db.commit()
    await db.refresh(lgu)
    return lgu


@router.put("/lgus/{lgu_id}", response_model=LGUOut)
async def update_lgu(
    lgu_id: int,
    payload: LGUUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    lgu = await db.get(LGU, lgu_id)
    if lgu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LGU not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lgu, field, value)
    await db.commit()
    await db.refresh(lgu)
    return lgu


@router.post("/lgus/{lgu_id}/verify", response_model=LGUOut)
async def verify_lgu(
    lgu_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    lgu = await db.get(LGU, lgu_id)
    if lgu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LGU not found")
    lgu.verified = True
    await db.commit()
    await db.refresh(lgu)
    return lgu


# --- System-wide analytics ---------------------------------------------------
@router.get("/analytics")
async def system_analytics(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users_by_role = dict(
        (await db.execute(select(User.role, func.count()).group_by(User.role))).all()
    )
    donations_by_status = dict(
        (
            await db.execute(
                select(Donation.status, func.count()).group_by(Donation.status)
            )
        ).all()
    )
    return {
        "users_by_role": {r.value: c for r, c in users_by_role.items()},
        "donations_by_status": {s.value: c for s, c in donations_by_status.items()},
        "total_lgus": (
            await db.execute(select(func.count()).select_from(LGU))
        ).scalar_one(),
        "verified_lgus": (
            await db.execute(
                select(func.count()).select_from(LGU).where(LGU.verified.is_(True))
            )
        ).scalar_one(),
        "completed_donations": (
            await db.execute(
                select(func.count()).select_from(Donation).where(
                    Donation.status == DonationStatus.completed
                )
            )
        ).scalar_one(),
    }
