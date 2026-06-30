"""ResQBites backend entrypoint.

Public endpoints (root, health, signup, login, logout) are defined inline here.
Every other resource lives in its own router under app/routes/ and is registered
with no prefix (each route declares its full path).
"""
import logging

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.auth import get_current_user  # noqa: F401  (re-exported for convenience)
from app.db.models import Base, User, UserRole
from app.db.session import AsyncSessionLocal, engine
from app.routes import (
    admin,
    analytics,
    dashboard,
    donations,
    lgu,
    notifications,
    onboarding,
    users,
)
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest
from app.schemas.common import Message
from app.services.security import (
    create_access_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger("resqbites")

app = FastAPI(
    title="ResQBites API",
    version="0.1.0",
    description="Backend for ResQBites — food-donation platform (Cebu City).",
)


@app.on_event("startup")
async def on_startup() -> None:
    """Create tables if missing. DB failure is non-fatal (service still boots)."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database ready.")
    except Exception as exc:  # pragma: no cover - defensive, matches reference
        logger.warning("Database init skipped/failed: %s", exc)


# --- Public endpoints --------------------------------------------------------
@app.get("/", tags=["meta"])
async def root():
    return {"service": "ResQBites API", "status": "ok"}


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "healthy"}


@app.post("/auth/signup", response_model=AuthResponse, tags=["auth"])
async def signup(payload: SignupRequest):
    # Self-registration is for donors and LGU accounts only; admins are seeded.
    if payload.role not in (UserRole.individual, UserRole.establishment, UserRole.lgu):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot self-register as this role")

    async with AsyncSessionLocal() as db:
        user = User(
            email=str(payload.email).lower(),
            password_hash=hash_password(payload.password),
            role=payload.role,
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.phone,
        )
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        await db.refresh(user)
        token = create_access_token(user.id, user.email, user.role.value)
        return AuthResponse(user_id=user.id, email=user.email, role=user.role, token=token)


@app.post("/auth/login", response_model=AuthResponse, tags=["auth"])
async def login(payload: LoginRequest):
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == str(payload.email).lower()))
        ).scalars().first()
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")
        token = create_access_token(user.id, user.email, user.role.value)
        return AuthResponse(user_id=user.id, email=user.email, role=user.role, token=token)


@app.post("/auth/logout", response_model=Message, tags=["auth"])
async def logout():
    """JWTs are stateless — the client discards the token. No-op server side."""
    return Message(detail="logged out")


# --- Router registration -----------------------------------------------------
app.include_router(onboarding.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(donations.router)
app.include_router(lgu.router)
app.include_router(analytics.router)
app.include_router(admin.router)
