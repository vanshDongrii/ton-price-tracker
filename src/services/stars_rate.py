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
    """Service to retrieve legitimate TON -> Telegram Stars conversion rates if available."""

    def __init__(
        self,
        source: str = "none",
        api_key: Optional[str] = None,
        custom_api_url: Optional[str] = None,
        api_timeout_seconds: float = 5.0,
        cache_ttl_seconds: int = 300,
    ):
        self.source = source.lower()
        self.api_key = api_key
        self.custom_api_url = custom_api_url
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
        force_refresh: bool = False,
    ) -> tuple[Optional[float], Optional[datetime], str]:
        """Retrieve TON -> Telegram Stars rate.
        
        Returns:
            tuple of (stars_per_ton, timestamp_utc, source_name).
            If no verified live rate exists, stars_per_ton is None.
        """
        # If explicitly disabled or set to none, return None immediately
        if self.source in ("", "none", "disabled", "false"):
            logger.debug("Telegram Stars conversion source is set to '%s' (unavailable by design)", self.source)
            return None, None, "Unavailable"

        cache_key = f"stars_rate_{self.source}"
        if not force_refresh:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        # If a custom API source is specified
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

                # Expecting JSON like {"ton_stars": 125.5} or {"rate": 125.5}
                rate_val = data.get("ton_stars") or data.get("rate") or data.get("stars")
                if rate_val is not None:
                    rate = float(rate_val)
                    now_utc = datetime.now(timezone.utc)
                    res = (rate, now_utc, "Custom API")
                    await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
                    return res
            except Exception as e:
                logger.warning("Custom Stars rate source request failed: %s", e)

        # If configured for Fragment platform
        if self.source == "fragment":
            # Fragment uses auction-based purchases for stars packages with TON.
            # Without authenticated Telegram/Fragment session keys, public rate is not exposed via an open floating API.
            logger.info("Fragment Stars source configured, but public open ticker API is not available")
            return None, None, "Fragment"

        logger.debug("No live Telegram Stars rate available for source: %s", self.source)
        return None, None, "Unavailable"
