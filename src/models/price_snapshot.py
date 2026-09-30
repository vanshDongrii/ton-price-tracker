"""Price snapshot model and freshness evaluation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Freshness(str, Enum):
    """Freshness states for market data."""

    LIVE = "live"
    DELAYED = "delayed"
    UNAVAILABLE = "unavailable"

    @property
    def badge(self) -> str:
        """Emoji badge representation."""
        if self == Freshness.LIVE:
            return "🟢 Live market data"
        if self == Freshness.DELAYED:
            return "🟡 Data delayed"
        return "🔴 Price unavailable"

    @property
    def short_label(self) -> str:
        """Short label for Live mode messages."""
        if self == Freshness.LIVE:
            return "🟢 LIVE"
        if self == Freshness.DELAYED:
            return "🟡 DELAYED"
        return "🔴 UNAVAILABLE"


@dataclass(frozen=True)
class PriceSnapshot:
    """Internal representation of a point-in-time price snapshot across all pairs."""

    ton_usdt: Optional[float] = None
    usd_inr: Optional[float] = None
    ton_inr: Optional[float] = None
    ton_stars: Optional[float] = None

    ton_usdt_timestamp: Optional[datetime] = None
    usd_inr_timestamp: Optional[datetime] = None
    ton_inr_timestamp: Optional[datetime] = None
    stars_timestamp: Optional[datetime] = None

    source: str = "Unknown"
    feed_type: str = "REST"  # "WebSocket" or "REST"

    def get_ton_usdt_freshness(self, stale_after_seconds: int = 15, now_utc: Optional[datetime] = None) -> Freshness:
        """Check freshness of the TON/USDT price."""
        if self.ton_usdt is None or self.ton_usdt_timestamp is None:
            return Freshness.UNAVAILABLE

        now = now_utc or datetime.now(timezone.utc)
        ts = self.ton_usdt_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        age = (now - ts).total_seconds()
        if age <= stale_after_seconds:
            return Freshness.LIVE
        return Freshness.DELAYED

    def get_usd_inr_freshness(self, stale_after_seconds: int = 86400, now_utc: Optional[datetime] = None) -> Freshness:
        """Check freshness of the USD/INR FX rate (FX updates daily/hourly)."""
        if self.usd_inr is None or self.usd_inr_timestamp is None:
            return Freshness.UNAVAILABLE

        now = now_utc or datetime.now(timezone.utc)
        ts = self.usd_inr_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        age = (now - ts).total_seconds()
        if age <= stale_after_seconds:
            return Freshness.LIVE
        return Freshness.DELAYED

    def get_ton_inr_freshness(self, stale_after_seconds: int = 15, now_utc: Optional[datetime] = None) -> Freshness:
        """Check freshness of TON/INR.
        
        Requires both TON/USDT and USD/INR to be valid.
        If either is stale or delayed relative to its threshold, marked DELAYED.
        """
        if self.ton_inr is None or self.ton_usdt is None or self.usd_inr is None:
            return Freshness.UNAVAILABLE

        ton_freshness = self.get_ton_usdt_freshness(stale_after_seconds, now_utc)
        if ton_freshness != Freshness.LIVE:
            return ton_freshness

        # FX is delayed if older than 24 hours (86400s)
        fx_freshness = self.get_usd_inr_freshness(86400, now_utc)
        if fx_freshness != Freshness.LIVE:
            return Freshness.DELAYED

        return Freshness.LIVE

    def get_stars_freshness(self, stale_after_seconds: int = 300, now_utc: Optional[datetime] = None) -> Freshness:
        """Check freshness of the Telegram Stars rate."""
        if self.ton_stars is None or self.stars_timestamp is None:
            return Freshness.UNAVAILABLE

        now = now_utc or datetime.now(timezone.utc)
        ts = self.stars_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        age = (now - ts).total_seconds()
        if age <= stale_after_seconds:
            return Freshness.LIVE
        return Freshness.DELAYED

    def get_overall_freshness(self, stale_after_seconds: int = 15, now_utc: Optional[datetime] = None) -> Freshness:
        """Overall market data freshness for the primary TON price."""
        return self.get_ton_usdt_freshness(stale_after_seconds, now_utc)

    @property
    def latest_timestamp(self) -> Optional[datetime]:
        """Return the most relevant timestamp among available values."""
        return self.ton_usdt_timestamp or self.ton_inr_timestamp or self.usd_inr_timestamp
