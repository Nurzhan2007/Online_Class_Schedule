"""FastAPI dependencies for authentication and role-based access control.

Usage in a router::

    @router.get("/admin/users")
    def list_users(admin: User = Depends(require_roles(Role.ADMIN))): ...

* no / bad / revoked token  -> 401 auth.loginFirst
* expired token             -> 401 auth.sessionExpired
* valid token, wrong role   -> 403 auth.denied

The role is always read from the database, never trusted from the token,
so a role change takes effect immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.errors import ApiError
from app.models import User
from app.roles import Role
from app.security import TokenError, TokenExpiredError, decode_access_token
from app.services.auth import is_token_revoked

# tokenUrl powers the "Authorize" button in Swagger (/api/docs).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    user: User
    jti: str
    expires_at: datetime  # naive UTC, same as in the database


def _unauthorized(code: str) -> ApiError:
    return ApiError(401, code, headers={"WWW-Authenticate": "Bearer"})


def get_auth_context(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    if not token:
        raise _unauthorized("auth.loginFirst")

    try:
        payload = decode_access_token(token, settings)
    except TokenExpiredError:
        raise _unauthorized("auth.sessionExpired") from None
    except TokenError:
        raise _unauthorized("auth.loginFirst") from None

    if is_token_revoked(db, payload["jti"]):
        raise _unauthorized("auth.loginFirst")

    user = db.get(User, int(payload["sub"]))
    if user is None:  # account was deleted after the token was issued
        raise _unauthorized("auth.loginFirst")

    expires_at = datetime.fromtimestamp(payload["exp"], timezone.utc).replace(tzinfo=None)
    return AuthContext(user=user, jti=payload["jti"], expires_at=expires_at)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


def require_roles(*roles: Role) -> Callable[..., User]:
    """Dependency factory: allow only users whose role is in ``roles``."""
    if not roles:
        raise ValueError("require_roles() needs at least one role")
    allowed = frozenset(roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ApiError(403, "auth.denied")
        return user

    return dependency


require_student = require_roles(Role.STUDENT)
require_teacher = require_roles(Role.TEACHER)
require_admin = require_roles(Role.ADMIN)
