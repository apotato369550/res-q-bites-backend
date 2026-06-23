"""ORM models for ResQBites.

All tables live here (the reference keeps a single models module). Conventions:
- ``created_at`` uses a server default of ``func.now()``.
- Categorical columns use SQL ``Enum`` backed by Python ``enum.Enum``.
- Structured/freeform fields use ``JSON``.
- Child rows FK to their parent with ``ondelete="CASCADE"``.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Enums -------------------------------------------------------------------
class UserRole(str, enum.Enum):
    individual = "individual"
    establishment = "establishment"
    lgu = "lgu"
    admin = "admin"


class EstablishmentType(str, enum.Enum):
    restaurant = "restaurant"
    hotel = "hotel"
    grocery = "grocery"
    bakery = "bakery"
    catering = "catering"
    other = "other"


class FoodCategory(str, enum.Enum):
    cooked_meal = "cooked_meal"
    baked_goods = "baked_goods"
    vegetables = "vegetables"
    fruits = "fruits"
    canned_goods = "canned_goods"
    mixed = "mixed"


class DonationMethod(str, enum.Enum):
    pickup = "pickup"
    dropoff = "dropoff"


class DonationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    scheduled = "scheduled"
    rejected = "rejected"
    completed = "completed"
    cancelled = "cancelled"


class FoodSafetyStatus(str, enum.Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"


class InventoryStatus(str, enum.Enum):
    in_stock = "in_stock"
    distributed = "distributed"
    expired = "expired"


# --- Phase 1: core -----------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # For role == lgu: which LGU this account administers.
    managing_lgu_id: Mapped[int | None] = mapped_column(
        ForeignKey("lgus.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    establishment_profile: Mapped["EstablishmentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    donations: Mapped[list["Donation"]] = relationship(
        back_populates="donor", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    managing_lgu: Mapped["LGU | None"] = relationship(foreign_keys=[managing_lgu_id])


class EstablishmentProfile(Base):
    __tablename__ = "establishment_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    establishment_name: Mapped[str] = mapped_column(String(200), nullable=False)
    establishment_type: Mapped[EstablishmentType] = mapped_column(
        Enum(EstablishmentType), nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(400))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="establishment_profile")


class LGU(Base):
    __tablename__ = "lgus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(400))
    contact_number: Mapped[str | None] = mapped_column(String(40))
    barangay: Mapped[str | None] = mapped_column(String(120), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    donations: Mapped[list["Donation"]] = relationship(back_populates="lgu")


class Donation(Base):
    __tablename__ = "donations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    donor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lgu_id: Mapped[int | None] = mapped_column(
        ForeignKey("lgus.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[str | None] = mapped_column(String(120))
    food_category: Mapped[FoodCategory] = mapped_column(Enum(FoodCategory), nullable=False)
    quote: Mapped[str | None] = mapped_column(Text)  # donor's message attached to the donation
    photo_base64: Mapped[str | None] = mapped_column(Text)  # base64-encoded image
    pickup_location: Mapped[str | None] = mapped_column(String(400))
    dropoff_location: Mapped[str | None] = mapped_column(String(400))
    donation_method: Mapped[DonationMethod] = mapped_column(
        Enum(DonationMethod), nullable=False
    )
    status: Mapped[DonationStatus] = mapped_column(
        Enum(DonationStatus), default=DonationStatus.pending, nullable=False, index=True
    )
    scheduled_pickup_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    donor: Mapped["User"] = relationship(back_populates="donations")
    lgu: Mapped["LGU | None"] = relationship(back_populates="donations")
    history: Mapped[list["DonationHistory"]] = relationship(
        back_populates="donation", cascade="all, delete-orphan",
        order_by="DonationHistory.created_at",
    )


class DonationHistory(Base):
    __tablename__ = "donation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    donation_id: Mapped[int] = mapped_column(
        ForeignKey("donations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    donation: Mapped["Donation"] = relationship(back_populates="history")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="notifications")


# --- Phase 2: LGU operations -------------------------------------------------
class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lgu_id: Mapped[int] = mapped_column(
        ForeignKey("lgus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    donation_id: Mapped[int | None] = mapped_column(
        ForeignKey("donations.id", ondelete="SET NULL")
    )
    food_category: Mapped[FoodCategory] = mapped_column(Enum(FoodCategory), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    food_safety_status: Mapped[FoodSafetyStatus] = mapped_column(
        Enum(FoodSafetyStatus), default=FoodSafetyStatus.pending, nullable=False
    )
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[InventoryStatus] = mapped_column(
        Enum(InventoryStatus), default=InventoryStatus.in_stock, nullable=False, index=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lgu_id: Mapped[int] = mapped_column(
        ForeignKey("lgus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    household_size: Mapped[int | None] = mapped_column(Integer)
    barangay: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(400))
    contact: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Distribution(Base):
    __tablename__ = "distributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lgu_id: Mapped[int] = mapped_column(
        ForeignKey("lgus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    beneficiary_id: Mapped[int] = mapped_column(
        ForeignKey("beneficiaries.id", ondelete="CASCADE"), nullable=False
    )
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    distributed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["DistributionItem"]] = relationship(
        back_populates="distribution", cascade="all, delete-orphan"
    )


class DistributionItem(Base):
    __tablename__ = "distribution_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    distribution_id: Mapped[int] = mapped_column(
        ForeignKey("distributions.id", ondelete="CASCADE"), nullable=False
    )
    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    distribution: Mapped["Distribution"] = relationship(back_populates="items")


# --- Phase 3: gamification, admin, analytics ---------------------------------
class PointsLedger(Base):
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    donation_id: Mapped[int | None] = mapped_column(
        ForeignKey("donations.id", ondelete="SET NULL")
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    threshold_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    badge_id: Mapped[int] = mapped_column(
        ForeignKey("badges.id", ondelete="CASCADE"), nullable=False
    )
    awarded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RewardRule(Base):
    __tablename__ = "reward_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    points_per_donation: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BarangayCoverage(Base):
    __tablename__ = "barangay_coverage"
    __table_args__ = (UniqueConstraint("lgu_id", "barangay", name="uq_lgu_barangay"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lgu_id: Mapped[int] = mapped_column(
        ForeignKey("lgus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    barangay: Mapped[str] = mapped_column(String(120), nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    value: Mapped[dict | None] = mapped_column(JSON)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
