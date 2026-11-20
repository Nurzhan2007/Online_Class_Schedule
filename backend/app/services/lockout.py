"""Account lockout rules (pure functions, no database).

Rules (same as the original frontend, but enforced on the server):

* every wrong password for an email increases its failure counter;
* reaching ``max_attempts`` consecutive failures locks the email for
  ``lockout_minutes``; while locked, even the correct password is refused;
* a successful login resets the counter;
* when a lock expires, counting starts again from zero.

Failures are tracked per normalised email, also for emails that have no
account, so the responses never reveal which emails are registered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class FailureResult:
    failed_count: int
    locked_until: datetime | None
    attempts_left: int

    @property
    def locked(self) -> bool:
        return self.locked_until is not None


def lock_remaining_seconds(locked_until: datetime | None, now: datetime) -> int:
    """Whole seconds until the lock ends (rounded up); 0 if not locked."""
    if locked_until is None or locked_until <= now:
        return 0
    return math.ceil((locked_until - now).total_seconds())


def register_failure(
    failed_count: int,
    now: datetime,
    max_attempts: int,
    lockout_minutes: int,
) -> FailureResult:
    new_count = failed_count + 1
    locked_until = now + timedelta(minutes=lockout_minutes) if new_count >= max_attempts else None
    return FailureResult(
        failed_count=new_count,
        locked_until=locked_until,
        attempts_left=max(0, max_attempts - new_count),
    )
