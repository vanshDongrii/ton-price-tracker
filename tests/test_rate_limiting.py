"""Unit tests for user rate limiting mechanism."""

import time
import pytest

from src.bot.rate_limiter import UserRateLimiter


def test_rate_limiter_allows_initial_request():
    """A fresh user should always be allowed."""
    limiter = UserRateLimiter(cooldown_seconds=3.0)
    allowed, remaining = limiter.check(user_id=123)
    assert allowed is True
    assert remaining == 0.0


def test_rate_limiter_blocks_rapid_second_request():
    """A second request within cooldown must be blocked."""
    limiter = UserRateLimiter(cooldown_seconds=3.0)
    allowed1, _ = limiter.check(user_id=123)
    assert allowed1 is True

    allowed2, remaining2 = limiter.check(user_id=123)
    assert allowed2 is False
    assert 0 < remaining2 <= 3.0


def test_rate_limiter_tracks_users_independently():
    """User A's rate limit must not affect User B."""
    limiter = UserRateLimiter(cooldown_seconds=3.0)

    # User A requests
    assert limiter.check(user_id=101)[0] is True
    # User A is now blocked
    assert limiter.check(user_id=101)[0] is False

    # User B should still be allowed
    assert limiter.check(user_id=102)[0] is True


def test_rate_limiter_reset():
    """Resetting a user allows immediate subsequent request."""
    limiter = UserRateLimiter(cooldown_seconds=3.0)
    limiter.check(user_id=123)
    assert limiter.check(user_id=123)[0] is False

    limiter.reset(user_id=123)
    assert limiter.check(user_id=123)[0] is True
