"""Application settings.

Values come from environment variables. For local development they can be
put into ``backend/.env`` (see ``.env.example``). Real environment variables
always win over values from the .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

DEFAULT_FRONTEND_DIR = PROJECT_ROOT / "online-class-schedule"
DEFAULT_DATABASE_URL = "sqlite:///" + (BACKEND_DIR / "kbtu.db").as_posix()
DEFAULT_CORS_ORIGINS = "http://127.0.0.1:5500,http://localhost:5500"

MIN_SECRET_KEY_LENGTH = 32
# Placeholder values that must never be accepted as a real key.
FORBIDDEN_SECRET_KEYS = {"change-me", "changeme", "secret", "your-secret-key"}

SECRET_KEY_HELP = (
    "Generate one with:  python -c \"import secrets; print(secrets.token_hex(32))\"  "
    "and put it into backend/.env as SECRET_KEY=..."
)


class ConfigError(ValueError):
    """Raised when the configuration is missing or unsafe."""


def _validate_secret_key(raw: str | None) -> str:
    key = (raw or "").strip()
    if not key:
        raise ConfigError("SECRET_KEY is not set. " + SECRET_KEY_HELP)
    if key.lower() in FORBIDDEN_SECRET_KEYS:
        raise ConfigError("SECRET_KEY is a placeholder value. " + SECRET_KEY_HELP)
    if len(key) < MIN_SECRET_KEY_LENGTH:
        raise ConfigError(
            f"SECRET_KEY is too short ({len(key)} characters, "
            f"minimum {MIN_SECRET_KEY_LENGTH}). " + SECRET_KEY_HELP
        )
    return key


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"{name} must be a positive integer, got {value}")
    return value


def _get_list(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_url: str
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    max_login_attempts: int
    lockout_minutes: int
    cors_origins: tuple[str, ...]
    frontend_dir: Path

    def __repr__(self) -> str:  # never print the secret key in logs
        return f"Settings(app_name={self.app_name!r}, database_url={self.database_url!r}, ...)"

    @classmethod
    def from_env(cls) -> "Settings":
        # No fallback: the app refuses to start without a strong key,
        # otherwise anyone could forge JWTs with a publicly known default.
        return cls(
            app_name=os.getenv("APP_NAME", "KBTU University Information System"),
            database_url=os.getenv("DATABASE_URL", "").strip() or DEFAULT_DATABASE_URL,
            secret_key=_validate_secret_key(os.getenv("SECRET_KEY")),
            jwt_algorithm="HS256",
            access_token_expire_minutes=_get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 30),
            max_login_attempts=_get_int("MAX_LOGIN_ATTEMPTS", 3),
            lockout_minutes=_get_int("LOCKOUT_MINUTES", 5),
            cors_origins=_get_list("CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
            frontend_dir=Path(os.getenv("FRONTEND_DIR", "").strip() or DEFAULT_FRONTEND_DIR),
        )


@lru_cache
def get_settings() -> Settings:
    # override=False: variables already set in the environment are kept.
    load_dotenv(BACKEND_DIR / ".env", override=False)
    return Settings.from_env()
