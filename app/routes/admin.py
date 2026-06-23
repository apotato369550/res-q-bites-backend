"""Admin surface — CSV #22-#29.

Users, LGU accounts + verification, system-wide analytics, reward rules,
barangay coverage, settings, audit logs.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.db.models import (
    LGU,
    AuditLog,
    BarangayCoverage,
    Donation,
    DonationStatus,
    RewardRule,
    SystemSetting,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.admin import (
    AdminUserOut,
    AdminUserUpdate,
    AuditLogOut,
    BarangayCoverageCreate,
    BarangayCoverageOut,
    LGUCreate,
    LGUUpdate,
    RewardRuleCreate,
    RewardRuleOut,
    RewardRuleUpdate,
    SettingOut,
    SettingUpsert,
)
from app.schemas.common import Message
from app.schemas.donation import LGUOut

router = APIRouter(prefix="/admin", tags=["admin"])


async def _audit(db: AsyncSession, actor_id: int, action: str, entity_type: str,
                 entity_id: int | None, detail: dict | None = None) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
        )
    )


# --- Users (#22) -------------------------------------------------------------
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
    await _audit(db, current_user.id, "update_user", "user", user.id, data)
    await db.commit()
    await db.refresh(user)
    return user


# --- LGUs (#23, #24) ---------------------------------------------------------
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
    await db.flush()
    await _audit(db, current_user.id, "create_lgu", "lgu", lgu.id)
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
    await _audit(db, current_user.id, "update_lgu", "lgu", lgu.id)
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
    await _audit(db, current_user.id, "verify_lgu", "lgu", lgu.id)
    await db.commit()
    await db.refresh(lgu)
    return lgu


# --- System-wide analytics (#25) ---------------------------------------------
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


# --- Reward rules (#26) ------------------------------------------------------
@router.get("/reward-rules", response_model=list[RewardRuleOut])
async def list_reward_rules(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return (
        await db.execute(select(RewardRule).order_by(RewardRule.id.desc()))
    ).scalars().all()


@router.post("/reward-rules", response_model=RewardRuleOut, status_code=status.HTTP_201_CREATED)
async def create_reward_rule(
    payload: RewardRuleCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Only one active rule at a time: deactivate others if this one is active.
    rule = RewardRule(**payload.model_dump())
    if rule.active:
        for other in (await db.execute(select(RewardRule).where(RewardRule.active.is_(True)))).scalars().all():
            other.active = False
    db.add(rule)
    await _audit(db, current_user.id, "create_reward_rule", "reward_rule", None)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/reward-rules/{rule_id}", response_model=RewardRuleOut)
async def update_reward_rule(
    rule_id: int,
    payload: RewardRuleUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rule = await db.get(RewardRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reward rule not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("active"):
        for other in (
            await db.execute(
                select(RewardRule).where(RewardRule.active.is_(True), RewardRule.id != rule_id)
            )
        ).scalars().all():
            other.active = False
    for field, value in data.items():
        setattr(rule, field, value)
    await _audit(db, current_user.id, "update_reward_rule", "reward_rule", rule.id)
    await db.commit()
    await db.refresh(rule)
    return rule


# --- Barangay coverage (#27) -------------------------------------------------
@router.get("/barangay-coverage", response_model=list[BarangayCoverageOut])
async def list_coverage(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return (await db.execute(select(BarangayCoverage))).scalars().all()


@router.post("/barangay-coverage", response_model=BarangayCoverageOut,
             status_code=status.HTTP_201_CREATED)
async def add_coverage(
    payload: BarangayCoverageCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(LGU, payload.lgu_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LGU not found")
    coverage = BarangayCoverage(**payload.model_dump())
    db.add(coverage)
    await db.commit()
    await db.refresh(coverage)
    return coverage


@router.delete("/barangay-coverage/{coverage_id}", response_model=Message)
async def remove_coverage(
    coverage_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    coverage = await db.get(BarangayCoverage, coverage_id)
    if coverage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coverage not found")
    await db.delete(coverage)
    await db.commit()
    return Message(detail="coverage removed")


# --- Settings (#28) ----------------------------------------------------------
@router.get("/settings", response_model=list[SettingOut])
async def list_settings(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return (await db.execute(select(SystemSetting))).scalars().all()


@router.put("/settings", response_model=SettingOut)
async def upsert_setting(
    payload: SettingUpsert,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    setting = (
        await db.execute(select(SystemSetting).where(SystemSetting.key == payload.key))
    ).scalars().first()
    if setting is None:
        setting = SystemSetting(key=payload.key, value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
    await _audit(db, current_user.id, "upsert_setting", "system_setting", None,
                 {"key": payload.key})
    await db.commit()
    await db.refresh(setting)
    return setting


# --- Audit logs (#29) --------------------------------------------------------
@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    limit: int = Query(default=100, le=500),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    return (await db.execute(stmt)).scalars().all()
