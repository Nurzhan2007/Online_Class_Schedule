"""Account creation, login with lockout, token issuing and revocation."""

from __future__ import annotations

import threading
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import ApiError
from app.models import LoginAttempt, RevokedToken, User, utcnow_naive
from app.roles import Role
from app.schemas import TokenResponse, UserOut, normalize_email
from app.security import (
    create_access_token,
    dummy_password_hash,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.services.lockout import lock_remaining_seconds, register_failure

# Login attempts are processed one at a time, so parallel requests cannot
# race past the counter and get more than MAX_LOGIN_ATTEMPTS guesses.
# This is enough for a single uvicorn process (how this project runs).
_login_guard = threading.Lock()


# ---------------------------------------------------------------- accounts

def create_user(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: Role,
    student_id: str | None,
) -> User:
    email = normalize_email(email)

    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ApiError(409, "auth.emailTaken")
    if student_id and db.scalar(select(User.id).where(User.student_id == student_id)) is not None:
        raise ApiError(409, "auth.idTaken")

    user = User(
        name=name,
        email=email,
        student_id=student_id,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two identical registrations at the same moment: the UNIQUE constraint wins.
        db.rollback()
        raise ApiError(409, "auth.emailTaken") from None
    return user


# ---------------------------------------------------------------- login

def _locked_error(seconds: int) -> ApiError:
    return ApiError(429, "auth.locked", {"seconds": seconds}, headers={"Retry-After": str(seconds)})


def authenticate(db: Session, email: str, password: str, settings: Settings) -> User:
    """Return the user for a correct email/password, otherwise raise ApiError.

    401 auth.invalid {n: attempts left} - wrong email or password
    429 auth.locked  {seconds}          - too many failures, try later
    """
    email = normalize_email(email)

    with _login_guard:
        now = utcnow_naive()
        attempt = db.get(LoginAttempt, email)

        # 1) A locked email is refused BEFORE the password is checked.
        if attempt is not None and attempt.locked_until is not None:
            remaining = lock_remaining_seconds(attempt.locked_until, now)
            if remaining > 0:
                raise _locked_error(remaining)
            # The lock has expired: start counting from zero again.
            attempt.failed_count = 0
            attempt.locked_until = None

        user = db.scalar(select(User).where(User.email == email))
        # Unknown email: still run a full hash check so timing does not reveal it.
        password_ok = verify_password(password, user.password_hash if user else dummy_password_hash())

        if user is None or not password_ok:
            if attempt is None:
                attempt = LoginAttempt(email=email, failed_count=0)
                db.add(attempt)
            result = register_failure(
                attempt.failed_count, now, settings.max_login_attempts, settings.lockout_minutes
            )
            attempt.failed_count = result.failed_count
            attempt.locked_until = result.locked_until
            attempt.updated_at = now
            db.commit()

            if result.locked:
                raise _locked_error(settings.lockout_minutes * 60)
            raise ApiError(401, "auth.invalid", {"n": result.attempts_left},
                           headers={"WWW-Authenticate": "Bearer"})

        # 2) Success: forget previous failures.
        if attempt is not None:
            db.delete(attempt)
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        db.commit()
        return user


def issue_token(user: User, settings: Settings) -> TokenResponse:
    issued = create_access_token(user.id, user.role.value, settings)
    return TokenResponse(
        access_token=issued.token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


# ---------------------------------------------------------------- logout

def is_token_revoked(db: Session, jti: str) -> bool:
    return db.get(RevokedToken, jti) is not None


def revoke_token(db: Session, jti: str, user_id: int, expires_at: datetime) -> None:
    now = utcnow_naive()
    # Housekeeping: revoked tokens that have expired anyway are no longer needed.
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at <= now))
    if db.get(RevokedToken, jti) is None:
        db.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
    db.commit()
