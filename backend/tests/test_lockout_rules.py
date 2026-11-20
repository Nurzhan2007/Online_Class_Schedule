"""Lockout rules as pure functions (no FastAPI or database needed)."""

from datetime import datetime, timedelta

from app.services.lockout import lock_remaining_seconds, register_failure

NOW = datetime(2026, 11, 13, 12, 0, 0)


def test_first_two_failures_do_not_lock():
    first = register_failure(0, NOW, max_attempts=3, lockout_minutes=5)
    second = register_failure(first.failed_count, NOW, max_attempts=3, lockout_minutes=5)

    assert (first.failed_count, first.attempts_left, first.locked) == (1, 2, False)
    assert (second.failed_count, second.attempts_left, second.locked) == (2, 1, False)


def test_third_consecutive_failure_locks_for_5_minutes():
    third = register_failure(2, NOW, max_attempts=3, lockout_minutes=5)

    assert third.locked
    assert third.attempts_left == 0
    assert third.locked_until == NOW + timedelta(minutes=5)


def test_limits_are_configurable():
    result = register_failure(4, NOW, max_attempts=5, lockout_minutes=15)

    assert result.locked_until == NOW + timedelta(minutes=15)


def test_remaining_seconds():
    locked_until = NOW + timedelta(minutes=5)

    assert lock_remaining_seconds(locked_until, NOW) == 300
    assert lock_remaining_seconds(locked_until, NOW + timedelta(seconds=299.2)) == 1
    assert lock_remaining_seconds(locked_until, locked_until) == 0
    assert lock_remaining_seconds(locked_until, NOW + timedelta(minutes=6)) == 0
    assert lock_remaining_seconds(None, NOW) == 0
