"""Phase 3 schemas: gamification reads + admin surface."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


# --- Gamification ------------------------------------------------------------
class PointsLedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    donation_id: int | None = None
    points: int
    reason: str | None = None
    created_at: datetime


class PointsSummary(BaseModel):
    balance: int
    entries: list[PointsLedgerOut]


class BadgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None
    threshold_points: int


class UserBadgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    badge: BadgeOut
    awarded_at: datetime


# --- Admin: LGUs -------------------------------------------------------------
class LGUCreate(BaseModel):
    name: str
    address: str | None = None
    contact_number: str | None = None
    barangay: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LGUUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    contact_number: str | None = None
    barangay: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    verified: bool | None = None


# --- Admin: users ------------------------------------------------------------
class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: str | None = None


# --- Admin: reward rules -----------------------------------------------------
class RewardRuleCreate(BaseModel):
    name: str
    points_per_donation: int = 10
    active: bool = True


class RewardRuleUpdate(BaseModel):
    name: str | None = None
    points_per_donation: int | None = None
    active: bool | None = None


class RewardRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    points_per_donation: int
    active: bool
    created_at: datetime


# --- Admin: barangay coverage ------------------------------------------------
class BarangayCoverageCreate(BaseModel):
    lgu_id: int
    barangay: str


class BarangayCoverageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lgu_id: int
    barangay: str


# --- Admin: settings ---------------------------------------------------------
class SettingUpsert(BaseModel):
    key: str
    value: Any


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any | None = None


# --- Admin: audit logs -------------------------------------------------------
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None = None
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    detail: Any | None = None
    created_at: datetime


# --- Admin user listing ------------------------------------------------------
class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    points_balance: int
    created_at: datetime
