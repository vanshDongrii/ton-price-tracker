"""GRAM token rate service for TON <-> GRAM conversions."""

import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from src.cache import TTLCache

logger = logging.getLogger(__name__)

# Standard GRAM jetton contract address on The Open Network
DEFAULT_GRAM_CONTRACT = "EQC47093oX5Xhb0xuk2lCr2RhS8rj-vul61u4W2UH5ORmG_O"


class GramRateService:
    """Retrieves live TON <-> GRAM conversion rates from TonAPI and DEX endpoints."""

    def __init__(
        self,
        contract_address: str = DEFAULT_GRAM_CONTRACT,
        cache_ttl_seconds: int = 60,
        api_timeout_seconds: float = 5.0,
    ):
        self.contract_address = contract_address
        self.cache_ttl_seconds = cache_ttl_seconds
        self.api_timeout_seconds = api_timeout_seconds

        self._cache: TTLCache[tuple[float, datetime, str]] = TTLCache(
            default_ttl_seconds=float(cache_ttl_seconds)
        )
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.api_timeout_seconds),
                headers={"User-Agent": "TONPriceTrackerBot/1.0"},
                follow_redirects=True,
            )
        return self._http_client

    async def aclose(self) -> None:
        """Close underlying HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _fetch_tonapi(self) -> tuple[float, datetime, str]:
        """Fetch GRAM/TON rate from official TonAPI indexed DEX rates."""
        client = await self._get_client()
        url = f"https://tonapi.io/v2/rates?tokens={self.contract_address}&currencies=ton,usd"
        resp = await client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()

        data = resp.json()
        rates = data.get("rates", {})
        token_data = rates.get(self.contract_address, {})
        prices = token_data.get("prices", {})

        ton_per_gram = prices.get("TON")
        if ton_per_gram is None or float(ton_per_gram) <= 0:
            raise ValueError(f"TonAPI returned invalid TON price for GRAM: {prices}")

        gram_per_ton = 1.0 / float(ton_per_gram)
        now_utc = datetime.now(timezone.utc)
        return gram_per_ton, now_utc, "TonAPI"

    async def _fetch_stonfi(self, ton_usdt: Optional[float] = None) -> tuple[float, datetime, str]:
        """Fetch GRAM price from STON.fi DEX."""
        client = await self._get_client()
        url = f"https://api.ston.fi/v1/assets/{self.contract_address}"
        resp = await client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()

        data = resp.json()
        asset = data.get("asset", {})
        dex_usd = asset.get("dex_usd_price") or asset.get("dex_price_usd")
        if dex_usd is None or float(dex_usd) <= 0:
            raise ValueError(f"STON.fi returned invalid USD price for GRAM: {dex_usd}")

        gram_usd = float(dex_usd)
        if ton_usdt is None or ton_usdt <= 0:
            raise ValueError("ton_usdt is required to compute gram_per_ton from STON.fi USD price")

        gram_per_ton = ton_usdt / gram_usd
        now_utc = datetime.now(timezone.utc)
        return gram_per_ton, now_utc, "STON.fi (DEX)"

    async def _fetch_coingecko(self, ton_usdt: Optional[float] = None) -> tuple[float, datetime, str]:
        """Fetch GRAM price from CoinGecko as fallback."""
        client = await self._get_client()
        url = "https://api.coingecko.com/api/v3/simple/price?ids=gram&vs_currencies=usd,ton"
        resp = await client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()

        data = resp.json()
        gram_data = data.get("gram", {})
        if "ton" in gram_data and float(gram_data["ton"]) > 0:
            ton_per_gram = float(gram_data["ton"])
            gram_per_ton = 1.0 / ton_per_gram
            return gram_per_ton, datetime.now(timezone.utc), "CoinGecko"

        if "usd" in gram_data and float(gram_data["usd"]) > 0 and ton_usdt:
            gram_usd = float(gram_data["usd"])
            gram_per_ton = ton_usdt / gram_usd
            return gram_per_ton, datetime.now(timezone.utc), "CoinGecko"

        raise ValueError(f"CoinGecko missing GRAM price data: {data}")

    async def get_gram_rate(
        self,
        ton_usdt: Optional[float] = None,
        force_refresh: bool = False,
    ) -> tuple[Optional[float], Optional[datetime], str]:
        """Retrieve current GRAM per 1 TON conversion rate.

        Returns:
            tuple of (gram_per_ton, timestamp_utc, source_name).
            If no reliable live rate is available, gram_per_ton is None.
        """
        cache_key = "ton_gram_rate"
        if not force_refresh:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        logger.info("Fetching fresh TON <-> GRAM rate...")

        # 1. Try TonAPI (Direct TON-indexed rate)
        try:
            res = await self._fetch_tonapi()
            await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
            logger.info("Retrieved GRAM rate via TonAPI: 1 TON = %.2f GRAM", res[0])
            return res
        except Exception as e:
            logger.warning("TonAPI GRAM rate fetch failed: %s. Trying STON.fi fallback...", e)

        # 2. Try STON.fi DEX fallback
        try:
            res = await self._fetch_stonfi(ton_usdt=ton_usdt)
            await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
            logger.info("Retrieved GRAM rate via STON.fi: 1 TON = %.2f GRAM", res[0])
            return res
        except Exception as e:
            logger.warning("STON.fi GRAM rate fetch failed: %s. Trying CoinGecko fallback...", e)

        # 3. Try CoinGecko fallback
        try:
            res = await self._fetch_coingecko(ton_usdt=ton_usdt)
            await self._cache.set(cache_key, res, ttl_seconds=float(self.cache_ttl_seconds))
            logger.info("Retrieved GRAM rate via CoinGecko: 1 TON = %.2f GRAM", res[0])
            return res
        except Exception as e:
            logger.warning("CoinGecko GRAM rate fetch failed: %s", e)

        logger.error("All GRAM rate providers failed; returning unavailable")
        return None, None, "Unavailable"
