"""Settings parsing (pure Python, no FastAPI needed)."""

import pytest

from app.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_FRONTEND_DIR,
    ConfigError,
    Settings,
)

SETTING_VARS = [
    "APP_NAME",
    "DATABASE_URL",
    "SECRET_KEY",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "MAX_LOGIN_ATTEMPTS",
    "LOCKOUT_MINUTES",
    "CORS_ORIGINS",
    "FRONTEND_DIR",
]

GOOD_KEY = "k" * 64


@pytest.fixture()
def clean_env(monkeypatch):
    for name in SETTING_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults_match_the_original_frontend_rules(clean_env):
    clean_env.setenv("SECRET_KEY", GOOD_KEY)

    settings = Settings.from_env()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.jwt_algorithm == "HS256"
    # Same values as SESSION_DURATION / MAX_LOGIN_ATTEMPTS / LOCKOUT_DURATION in auth.js
    assert settings.access_token_expire_minutes == 30
    assert settings.max_login_attempts == 3
    assert settings.lockout_minutes == 5
    assert settings.frontend_dir == DEFAULT_FRONTEND_DIR


def test_default_frontend_dir_points_at_existing_frontend():
    assert (DEFAULT_FRONTEND_DIR / "index.html").is_file()
    assert (DEFAULT_FRONTEND_DIR / "js" / "app.js").is_file()


def test_values_can_be_overridden(clean_env):
    clean_env.setenv("SECRET_KEY", GOOD_KEY)
    clean_env.setenv("DATABASE_URL", "sqlite:///other.db")
    clean_env.setenv("LOCKOUT_MINUTES", "15")
    clean_env.setenv("MAX_LOGIN_ATTEMPTS", "5")
    clean_env.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    clean_env.setenv("CORS_ORIGINS", " http://a.test , ,http://b.test ")

    settings = Settings.from_env()

    assert settings.secret_key == GOOD_KEY
    assert settings.database_url == "sqlite:///other.db"
    assert settings.lockout_minutes == 15
    assert settings.max_login_attempts == 5
    assert settings.access_token_expire_minutes == 60
    assert settings.cors_origins == ("http://a.test", "http://b.test")


@pytest.mark.parametrize("bad_value", ["abc", "0", "-3", "1.5"])
def test_invalid_numbers_are_rejected(clean_env, bad_value):
    clean_env.setenv("SECRET_KEY", GOOD_KEY)
    clean_env.setenv("LOCKOUT_MINUTES", bad_value)

    with pytest.raises(ConfigError, match="LOCKOUT_MINUTES"):
        Settings.from_env()


def test_missing_secret_key_stops_the_app(clean_env):
    with pytest.raises(ConfigError, match="SECRET_KEY is not set"):
        Settings.from_env()


@pytest.mark.parametrize("bad_key", ["", "   ", "short-key", "change-me", "x" * 31])
def test_weak_secret_keys_are_rejected(clean_env, bad_key):
    clean_env.setenv("SECRET_KEY", bad_key)

    with pytest.raises(ConfigError, match="SECRET_KEY"):
        Settings.from_env()


def test_secret_key_of_minimum_length_is_accepted(clean_env):
    clean_env.setenv("SECRET_KEY", "x" * 32)

    assert Settings.from_env().secret_key == "x" * 32


def test_secret_key_is_not_shown_in_repr(clean_env):
    clean_env.setenv("SECRET_KEY", GOOD_KEY)

    assert GOOD_KEY not in repr(Settings.from_env())
