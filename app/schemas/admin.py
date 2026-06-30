"""Admin surface schemas: users and LGU management."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


# --- Admin: LGUs -------------------------------------------------------------
class LGUCreate(BaseModel):
    name: str
    address: str | None = None
    contact_number: str | None = None
    barangay: str | None = None


class LGUUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    contact_number: str | None = None
    barangay: str | None = None
    verified: bool | None = None


# --- Admin: users ------------------------------------------------------------
class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: str | None = None


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    created_at: datetime
