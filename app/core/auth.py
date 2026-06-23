"""Auth dependencies: current-user resolution and role gating."""
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import JWT_ALGORITHM, JWT_SECRET
from app.db.models import User, UserRole
from app.db.session import get_db

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the Bearer token and load the User. 401 on any failure."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHORIZED
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise _UNAUTHORIZED
        user_id = int(subject)
    except (JWTError, ValueError):
        raise _UNAUTHORIZED

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


def require_role(*roles: UserRole):
    """Dependency factory: 403 unless the current user holds one of ``roles``."""

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this resource",
            )
        return current_user

    return _checker


# Convenience role bundles
require_donor = require_role(UserRole.individual, UserRole.establishment)
require_lgu = require_role(UserRole.lgu)
require_admin = require_role(UserRole.admin)
