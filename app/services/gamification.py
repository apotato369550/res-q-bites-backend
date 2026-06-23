"""Points & badges — the single owner of the gamification rules.

``award_for_completion`` is invoked when an LGU marks a donation complete. It:
1. reads the active RewardRule (falls back to a default of 10 pts),
2. writes a PointsLedger row and bumps User.points_balance,
3. grants any newly-earned badges (by points threshold) + a notification.

Callers commit the surrounding transaction.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Badge,
    Donation,
    PointsLedger,
    RewardRule,
    User,
    UserBadge,
)
from app.services.notifications import notify

DEFAULT_POINTS_PER_DONATION = 10


async def _active_points_per_donation(db: AsyncSession) -> int:
    rule = (
        await db.execute(
            select(RewardRule).where(RewardRule.active.is_(True)).order_by(RewardRule.id.desc())
        )
    ).scalars().first()
    return rule.points_per_donation if rule else DEFAULT_POINTS_PER_DONATION


async def award_for_completion(db: AsyncSession, donation: Donation) -> int:
    """Award points + badges for a completed donation. Returns points awarded."""
    donor = await db.get(User, donation.donor_id)
    if donor is None:
        return 0

    points = await _active_points_per_donation(db)
    db.add(
        PointsLedger(
            user_id=donor.id,
            donation_id=donation.id,
            points=points,
            reason="donation_completed",
        )
    )
    donor.points_balance = (donor.points_balance or 0) + points

    await _grant_badges(db, donor)
    return points


async def _grant_badges(db: AsyncSession, donor: User) -> None:
    """Grant any badge whose threshold the donor now meets and doesn't yet hold."""
    eligible = (
        await db.execute(
            select(Badge).where(Badge.threshold_points <= donor.points_balance)
        )
    ).scalars().all()
    if not eligible:
        return

    owned = set(
        (
            await db.execute(
                select(UserBadge.badge_id).where(UserBadge.user_id == donor.id)
            )
        ).scalars().all()
    )
    for badge in eligible:
        if badge.id in owned:
            continue
        db.add(UserBadge(user_id=donor.id, badge_id=badge.id))
        await notify(
            db,
            donor.id,
            title="New badge earned!",
            message=f"You've earned the '{badge.name}' badge.",
        )
