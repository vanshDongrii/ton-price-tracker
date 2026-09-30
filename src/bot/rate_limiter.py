"""Per-user rate limiter to prevent spamming manual refresh commands."""

import time
from typing import Optional


class UserRateLimiter:
    """Sliding-window per-user cooldown limiter."""

    def __init__(self, cooldown_seconds: float = 3.0, max_tracked_users: int = 10000):
        self.cooldown = cooldown_seconds
        self.max_tracked_users = max_tracked_users
        self._user_timestamps: dict[int, float] = {}

    def check(self, user_id: int) -> tuple[bool, float]:
        """Check if user is allowed to perform a manual refresh.
        
        Returns:
            tuple of (is_allowed, remaining_seconds)
        """
        now = time.monotonic()

        # Housekeeping if tracked dict grows too large
        if len(self._user_timestamps) > self.max_tracked_users:
            cutoff = now - (self.cooldown * 10)
            self._user_timestamps = {
                uid: ts for uid, ts in self._user_timestamps.items() if ts > cutoff
            }

        last_time = self._user_timestamps.get(user_id)
        if last_time is not None:
            elapsed = now - last_time
            if elapsed < self.cooldown:
                remaining = self.cooldown - elapsed
                return False, round(remaining, 1)

        self._user_timestamps[user_id] = now
        return True, 0.0

    def reset(self, user_id: int) -> None:
        """Clear rate limit entry for a user."""
        self._user_timestamps.pop(user_id, None)
