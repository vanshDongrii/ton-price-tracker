"""Exchange rate service for USD/INR conversion with caching and fallback providers."""

import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from src.cache import TTLCache

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Retrieves live USD/INR exchange rates from reliable forex/crypto APIs."""

    def __init__(
        self,
        provider: str = "exchangerate-api",
        api_key: Optional[str] = None,
        cache_ttl_seconds: int = 300,
        api_timeout_seconds: float = 5.0,
    ):
        self.provider = provider.lower()
        self.api_key = api_key
        self.cache_ttl_seconds = cache_ttl_seconds
        self.api_timeout_seconds = api_timeout_seconds

        # In-memory cache for FX data
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
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _fetch_exchangerate_api(self) -> tuple[float, datetime, str]:
        """Fetch USD/INR rate from open ExchangeRate-API."""
        client = await self._get_client()
        url = "https://open.er-api.com/v6/latest/USD"
        resp = await client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()
        data = resp.json()

        rate = float(data["rates"]["INR"])
        ts_unix = data.get("time_last_update_unix")
        if ts_unix:
            ts = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        return rate, ts, "ExchangeRate-API"

    async def _fetch_frankfurter(self) -> tuple[float, datetime, str]:
        """Fetch USD/INR rate from Frankfurter (ECB data)."""
        client = await self._get_client()
        url = "https://api.frankfurter.app/latest?from=USD&to=INR"
        resp = await client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()
        data = resp.json()

        rate = float(data["rates"]["INR"])
        ts = datetime.now(timezone.utc)
        return rate, ts, "Frankfurter (ECB)"

    async def _fetch_coingecko_usdt_inr(self) -> tuple[float, datetime, str]:
        """Fetch USDT/INR rate from CoinGecko as fallback."""
        client = await self._get_client()
        url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=inr"
        resp = await client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()
        data = resp.json()

        rate = float(data["tether"]["inr"])
        ts = datetime.now(timezone.utc)
        return rate, ts, "CoinGecko (USDT/INR)"

    async def get_usd_inr_rate(
        self,
        force_refresh: bool = False,
    ) -> tuple[Optional[float], Optional[datetime], str]:
        """Retrieve current USD/INR exchange rate with caching and provider fallback.
        
        Returns:
            tuple of (rate, timestamp_utc, provider_name)
        """
        cache_key = "usd_inr_rate"

        if not force_refresh:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        logger.info("Fetching fresh USD/INR exchange rate (provider: %s)...", self.provider)

        # Primary provider
        rate_tuple: Optional[tuple[float, datetime, str]] = None
        try:
            if self.provider == "frankfurter":
                rate_tuple = await self._fetch_frankfurter()
            elif self.provider == "coingecko":
                rate_tuple = await self._fetch_coingecko_usdt_inr()
            else:
                rate_tuple = await self._fetch_exchangerate_api()
        except Exception as e:
            logger.warning("Primary FX provider '%s' failed: %s. Trying fallback...", self.provider, e)

        # Secondary fallback if primary failed
        if rate_tuple is None and self.provider != "exchangerate-api":
            try:
                rate_tuple = await self._fetch_exchangerate_api()
            except Exception as e:
                logger.warning("Secondary FX fallback (ExchangeRate-API) failed: %s", e)

        if rate_tuple is None and self.provider != "frankfurter":
            try:
                rate_tuple = await self._fetch_frankfurter()
            except Exception as e:
                logger.warning("Tertiary FX fallback (Frankfurter) failed: %s", e)

        if rate_tuple is not None:
            rate, ts, src = rate_tuple
            logger.info("Retrieved USD/INR: %.4f from %s", rate, src)
            await self._cache.set(cache_key, rate_tuple, ttl_seconds=float(self.cache_ttl_seconds))
            return rate, ts, src

        logger.error("All FX exchange rate providers failed")
        return None, None, "Unavailable"
