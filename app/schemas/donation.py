"""Donation, history, and LGU schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import (
    DonationMethod,
    DonationStatus,
    FoodCategory,
)


class DonationCreate(BaseModel):
    title: str
    description: str | None = None
    quantity: str | None = None
    food_category: FoodCategory
    quote: str | None = None
    photo_base64: str | None = None
    donation_method: DonationMethod
    pickup_location: str | None = None
    dropoff_location: str | None = None
    # Optional preferred LGU; otherwise an LGU picks it up from the pending queue.
    lgu_id: int | None = None


class DonationUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    quantity: str | None = None
    food_category: FoodCategory | None = None
    quote: str | None = None
    photo_base64: str | None = None
    donation_method: DonationMethod | None = None
    pickup_location: str | None = None
    dropoff_location: str | None = None


class DonationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    donor_id: int
    lgu_id: int | None = None
    title: str
    description: str | None = None
    quantity: str | None = None
    food_category: FoodCategory
    quote: str | None = None
    photo_base64: str | None = None
    donation_method: DonationMethod
    pickup_location: str | None = None
    dropoff_location: str | None = None
    status: DonationStatus
    scheduled_pickup_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DonationSummary(BaseModel):
    """List view — omits the heavy base64 photo payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    donor_id: int
    lgu_id: int | None = None
    title: str
    food_category: FoodCategory
    donation_method: DonationMethod
    status: DonationStatus
    scheduled_pickup_at: datetime | None = None
    created_at: datetime


class DonationHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    notes: str | None = None
    actor_id: int | None = None
    created_at: datetime


class ScheduleRequest(BaseModel):
    scheduled_pickup_at: datetime
    notes: str | None = None


class ActionNote(BaseModel):
    notes: str | None = None


class LGUOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str | None = None
    contact_number: str | None = None
    barangay: str | None = None
    verified: bool
