"""Auth & onboarding request/response schemas."""
from pydantic import BaseModel, EmailStr, Field

from app.db.models import EstablishmentType, UserRole


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Self-registration is limited to donors and LGU accounts (admins are seeded).
    role: UserRole = UserRole.individual
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: int
    email: EmailStr
    role: UserRole
    token: str


class IndividualOnboarding(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None


class EstablishmentOnboarding(BaseModel):
    establishment_name: str
    establishment_type: EstablishmentType
    address: str | None = None
    phone: str | None = None
