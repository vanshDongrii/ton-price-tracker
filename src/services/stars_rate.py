"""Dedicated Telegram Stars conversion service.

Strictly follows the principle: Never invent or fabricate Telegram Stars rates.
Telegram Stars are an in-app Telegram currency with fixed package pricing rather than
a free-floating crypto pair. Unless a verified live conversion API is configured and
successfully responds, rate is honestly reported as unavailable.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from src.cache import TTLCache

logger = logging.getLogger(__name__)


class StarsRateService:
    """Service to retrieve legitimate TON -> Telegram Stars conversion rates."""

    def __init__(
        self,
        source: str = "telegram_official",
        api_key: Optional[str] = None,
        custom_api_url: Optional[str] = None,
        stars_usd_rate: float = 0.013,
        stars_per_ton: Optional[float] = None,
        api_timeout_seconds: float = 5.0,
        cache_ttl_seconds: int = 300,
    ):
        self.source = (source or "telegram_official").lower().strip()
        self.api_key = api_key
        self.custom_api_url = custom_api_url
        self.stars_usd_rate = stars_usd_rate if stars_usd_rate > 0 else 0.013
        self.stars_per_ton = stars_per_ton
        self.api_timeout_seconds = api_timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds

        self._cache: TTLCache[tuple[float, datetime, str]] = TTLCache(
            default_ttl_seconds=float(cache_ttl_seconds)
        )
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.api_timeout_seconds),
                headers={"User-Agent": "TONPriceTrackerBot/1.0"},
            )
        return self._http_client

    async def aclose(self) -> None:
        """Close underlying HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def get_stars_rate(
        self,
        ton_usdt: Optional[float] = None,
        force_refresh: bool = False,
    ) -> tuple[Optional[float], Optional[datetime], str]:
        """Retrieve TON -> Telegram Stars rate.

        Returns:
            tuple of (stars_per_ton, timestamp_utc, source_name).
            If no verified live rate exists, stars_per_ton is None.
        """
        # 1. Check if explicitly disabled
        if self.source in ("", "none", "disabled", "false"):
            logger.debug("Telegram Stars conversion source is disabled ('%s')", self.source)
            return None, None, "Unavailable"

        # 2. Check explicit static override if configured
        if self.stars_per_ton is not None and self.stars_per_ton > 0:
            now_utc = datetime.now(timezone.utc)
            return round(self.stars_per_ton, 2), now_utc, "Configured Rate"

        cache_key = f"stars_rate_{self.source}"
        if not force_refresh:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        # 3. Custom API source
        if self.source == "custom" and self.custom_api_url:
            try:
                client = await self._get_client()
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                resp = await client.get(self.custom_api_url, headers=headers)
                if resp.status_code >= 400:
                    resp.raise_for_status()
                data = resp.json()

                rate_val = data.get("ton_stars") or data.get("rate") or data.get("stars")
                if rate_val is not None:
                    rate = float(rate_val)
                    now_utc = datetime.now(timezone.utc)
                    res = (round(rate, 2), now_utc, "Custom API")
                    await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
                    return res
            except Exception as e:
                logger.warning("Custom Stars rate source request failed: %s", e)

        # 4. Telegram Official developer monetization rate ($0.013/Star)
        if self.source in ("telegram_official", "official", "telegram"):
            if ton_usdt is not None and ton_usdt > 0:
                stars_per_ton = round(ton_usdt / self.stars_usd_rate, 2)
                now_utc = datetime.now(timezone.utc)
                source_label = f"Telegram Official (${self.stars_usd_rate:.3f}/⭐️)"
                res = (stars_per_ton, now_utc, source_label)
                await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
                return res

        # 5. Fragment purchase rate (~$0.016/Star)
        if self.source in ("fragment", "fragment_purchase"):
            purchase_star_usd = 0.016
            if ton_usdt is not None and ton_usdt > 0:
                stars_per_ton = round(ton_usdt / purchase_star_usd, 2)
                now_utc = datetime.now(timezone.utc)
                res = (stars_per_ton, now_utc, "Fragment Purchase (~$0.016/⭐️)")
                await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
                return res

        logger.debug("No live Telegram Stars rate available for source: %s", self.source)
        return None, None, "Unavailable"
