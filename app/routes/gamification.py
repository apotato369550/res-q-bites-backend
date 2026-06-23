"""Gamification reads: points ledger, badges, badge catalog — CSV #10, #11."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_donor
from app.db.models import Badge, PointsLedger, User, UserBadge
from app.db.session import get_db
from app.schemas.admin import (
    BadgeOut,
    PointsLedgerOut,
    PointsSummary,
    UserBadgeOut,
)

router = APIRouter(tags=["gamification"])


@router.get("/users/me/points", response_model=PointsSummary)
async def my_points(
    current_user: User = Depends(require_donor),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(PointsLedger)
        .where(PointsLedger.user_id == current_user.id)
        .order_by(PointsLedger.created_at.desc())
    )
    entries = (await db.execute(stmt)).scalars().all()
    return PointsSummary(
        balance=current_user.points_balance,
        entries=[PointsLedgerOut.model_validate(e) for e in entries],
    )


@router.get("/users/me/badges", response_model=list[UserBadgeOut])
async def my_badges(
    current_user: User = Depends(require_donor),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserBadge, Badge)
        .join(Badge, Badge.id == UserBadge.badge_id)
        .where(UserBadge.user_id == current_user.id)
        .order_by(UserBadge.awarded_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        UserBadgeOut(badge=BadgeOut.model_validate(badge), awarded_at=ub.awarded_at)
        for ub, badge in rows
    ]


@router.get("/badges", response_model=list[BadgeOut])
async def badge_catalog(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Badge).order_by(Badge.threshold_points)
    return (await db.execute(stmt)).scalars().all()
