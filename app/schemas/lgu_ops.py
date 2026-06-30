"""Phase 2 schemas: food-safety, inventory, beneficiaries, distribution."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import FoodCategory, FoodSafetyStatus, InventoryStatus


class FoodSafetyRequest(BaseModel):
    result: FoodSafetyStatus  # passed | failed (pending allowed but unusual)
    notes: str | None = None


class InventoryItemCreate(BaseModel):
    food_category: FoodCategory
    quantity: float = 0
    unit: str | None = None
    donation_id: int | None = None
    expiry_date: datetime | None = None
    food_safety_status: FoodSafetyStatus = FoodSafetyStatus.pending


class InventoryItemUpdate(BaseModel):
    quantity: float | None = None
    unit: str | None = None
    food_safety_status: FoodSafetyStatus | None = None
    expiry_date: datetime | None = None
    status: InventoryStatus | None = None


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lgu_id: int
    donation_id: int | None = None
    food_category: FoodCategory
    quantity: float
    unit: str | None = None
    food_safety_status: FoodSafetyStatus
    expiry_date: datetime | None = None
    status: InventoryStatus
    received_at: datetime


class BeneficiaryCreate(BaseModel):
    name: str
    household_size: int | None = None
    barangay: str | None = None
    address: str | None = None
    contact: str | None = None
    notes: str | None = None


class BeneficiaryUpdate(BaseModel):
    name: str | None = None
    household_size: int | None = None
    barangay: str | None = None
    address: str | None = None
    contact: str | None = None
    notes: str | None = None


class BeneficiaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lgu_id: int
    name: str
    household_size: int | None = None
    barangay: str | None = None
    address: str | None = None
    contact: str | None = None
    notes: str | None = None
    created_at: datetime


class DistributionCreate(BaseModel):
    beneficiary_id: int
    inventory_item_id: int
    quantity: float = Field(gt=0)
    notes: str | None = None


class DistributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lgu_id: int
    beneficiary_id: int
    inventory_item_id: int
    quantity: float
    recorded_by: int | None = None
    notes: str | None = None
    distributed_at: datetime
