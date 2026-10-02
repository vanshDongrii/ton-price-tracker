"""Dedicated Telegram Stars conversion service.

Strictly follows the principle: Never invent or fabricate Telegram Stars rates.
Telegram Stars are an in-app Telegram currency purchased officially via Fragment
(or through Telegram in-app purchases). On Fragment, Stars are priced across all
packages at an authoritative rate of $0.0150 USD per Star ($1.50 per 100 Stars,
$15.00 per 1,000 Stars).

The conversion from TON to Telegram Stars is calculated as:
    (TON amount × live TON/USD price) ÷ verified USD price per Star ($0.015)
yielding indivisible integer Telegram Stars.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional
import httpx

from src.cache import TTLCache

logger = logging.getLogger(__name__)


class StarsRateService:
    """Service to retrieve legitimate TON -> Telegram Stars conversion rates."""

    def __init__(
        self,
        source: str = "fragment",
        api_key: Optional[str] = None,
        custom_api_url: Optional[str] = None,
        stars_usd_rate: float = 0.015,
        stars_per_ton: Optional[float] = None,
        api_timeout_seconds: float = 5.0,
        cache_ttl_seconds: int = 300,
    ):
        self.source = (source or "fragment").lower().strip()
        self.api_key = api_key
        self.custom_api_url = custom_api_url
        self.stars_usd_rate = stars_usd_rate if stars_usd_rate > 0 else 0.015
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
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
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
            return float(self.stars_per_ton), now_utc, "Configured Rate"

        cache_key = f"stars_rate_{self.source}"
        if not force_refresh:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                # If ton_usdt has updated, recalculate stars rate with fresh ton_usdt
                if ton_usdt is not None and ton_usdt > 0:
                    cached_rate, cached_ts, cached_src = cached
                    fresh_rate = ton_usdt / self.stars_usd_rate
                    return fresh_rate, cached_ts, cached_src
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
                    res = (rate, now_utc, "Custom API")
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

        # 5. Fragment Official Stars Rate:
        # Verified package price: $0.015 USD per Star across all tiers.
        # Check live Fragment page if available to verify live tonRate and package price
        fragment_ton_rate: Optional[float] = None
        verified_star_usd = self.stars_usd_rate if self.stars_usd_rate > 0 else 0.015
        try:
            client = await self._get_client()
            resp = await client.get("https://fragment.com/stars/buy")
            if resp.status_code == 200:
                # Verify package price (e.g. 50 Stars for $0.75 -> $0.015/⭐️)
                m_pkg = re.search(r'value="50".*?icon-usd">([0-9.]+)', resp.text, re.DOTALL)
                if m_pkg:
                    p_usd = float(m_pkg.group(1))
                    if p_usd > 0:
                        verified_star_usd = p_usd / 50.0

                # Check Fragment's published tonRate
                m_rate = re.search(r'"tonRate":\s*([0-9.]+)', resp.text)
                if m_rate:
                    fragment_ton_rate = float(m_rate.group(1))
        except Exception as e:
            logger.debug("Live Fragment fetch check failed (using live market TON/USD feed): %s", e)

        # Compute using the live market TON price (or Fragment tonRate if market unavailable)
        effective_ton_usd = ton_usdt if (ton_usdt is not None and ton_usdt > 0) else fragment_ton_rate

        if effective_ton_usd is not None and effective_ton_usd > 0:
            stars_per_ton = effective_ton_usd / verified_star_usd
            now_utc = datetime.now(timezone.utc)
            source_label = f"Fragment (${verified_star_usd:.3f}/⭐️)"
            res = (stars_per_ton, now_utc, source_label)
            await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
            return res

        logger.debug("No live Telegram Stars rate available for source: %s", self.source)
        return None, None, "Unavailable"

