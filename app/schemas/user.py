"""User, profile, and notification schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.db.models import EstablishmentType, UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: UserRole
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    is_active: bool
    managing_lgu_id: int | None = None
    created_at: datetime
    # Establishment-donor fields (null for non-establishment accounts).
    establishment_name: str | None = None
    establishment_type: EstablishmentType | None = None
    establishment_address: str | None = None
    establishment_verified: bool | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str | None = None
    is_read: bool
    created_at: datetime
