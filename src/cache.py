"""In-memory TTL cache for reducing duplicate requests without hiding live data."""

import asyncio
import time
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    created_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


class TTLCache(Generic[T]):
    """Thread-safe and async-safe in-memory cache with explicit time-to-live."""

    def __init__(self, default_ttl_seconds: float = 60.0):
        self.default_ttl = default_ttl_seconds
        self._store: dict[str, CacheEntry[T]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """Retrieve value if present and not expired, else None."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._store[key]
                return None
            return entry.value

    async def set(self, key: str, value: T, ttl_seconds: Optional[float] = None) -> None:
        """Store value with specified or default TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = time.monotonic()
        async with self._lock:
            self._store[key] = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + ttl,
            )

    async def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._store.clear()

    async def get_created_at(self, key: str) -> Optional[float]:
        """Return monotonic timestamp when the entry was created."""
        async with self._lock:
            entry = self._store.get(key)
            if entry and not entry.is_expired:
                return entry.created_at
            return None
