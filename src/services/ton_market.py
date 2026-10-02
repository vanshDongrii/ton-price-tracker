"""TON market service combining WebSocket streaming with automatic REST fallback."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

from src.cache import TTLCache
from src.services.websocket_client import CryptoWebSocketClient

logger = logging.getLogger(__name__)


class TONMarketService:
    """Provides the latest live TON/USDT market price via WebSocket with automatic REST fallback."""

    def __init__(
        self,
        provider: str = "binance",
        symbol_pair: str = "TONUSDT",
        stale_threshold_seconds: int = 15,
        api_timeout_seconds: float = 5.0,
    ):
        self.provider = provider.lower()
        self.symbol_pair = symbol_pair.upper()
        self.stale_threshold_seconds = stale_threshold_seconds
        self.api_timeout_seconds = api_timeout_seconds

        # In-memory latest snapshot
        self._latest_price: Optional[float] = None
        self._latest_timestamp: Optional[datetime] = None
        self._latest_source: str = f"{self.provider.title()} (Initial)"
        self._feed_type: str = "Uninitialized"
        self._lock = asyncio.Lock()

        # Short cache for REST fallback to prevent duplicate calls during bursts
        self._rest_cache: TTLCache[float] = TTLCache[float](default_ttl_seconds=2.0)

        # Initialize WebSocket client
        self._ws_client = CryptoWebSocketClient(
            provider=self.provider,
            symbol_pair=self.symbol_pair,
            on_price_update=self._on_ws_tick,
            open_timeout=self.api_timeout_seconds,
        )

        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def is_ws_connected(self) -> bool:
        """Return True if the underlying WebSocket is currently connected."""
        return self._ws_client.is_connected

    async def _on_ws_tick(self, price: float, timestamp: datetime, source: str) -> None:
        """Callback invoked when a new tick arrives over WebSocket."""
        async with self._lock:
            self._latest_price = price
            self._latest_timestamp = timestamp
            self._latest_source = source
            self._feed_type = "WebSocket"
        logger.debug("Received WS tick: %s = %.4f from %s", self.symbol_pair, price, source)

    async def start(self) -> None:
        """Start the market service and start WebSocket feed."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.api_timeout_seconds),
                headers={"User-Agent": "TONPriceTrackerBot/1.0"},
                follow_redirects=True,
            )

        logger.info("Starting TONMarketService...")
        self._ws_client.start()

        # Prime with initial REST fetch so we have an immediate price before first tick
        try:
            await self._fetch_rest_fallback()
        except Exception as e:
            logger.warning("Initial REST price prime failed: %s", e)

    async def stop(self) -> None:
        """Stop WebSocket feed and close HTTP client."""
        logger.info("Stopping TONMarketService...")
        await self._ws_client.stop()
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _fetch_binance_rest(self) -> float:
        """Fetch latest price from Binance REST API."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized")

        url = f"https://api.binance.com/api/v3/ticker/price?symbol={self.symbol_pair}"
        resp = await self._http_client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or "price" not in data:
            raise ValueError(f"Unexpected Binance response format: {data}")
        price = float(data["price"])
        if price <= 0:
            raise ValueError(f"Invalid Binance price: {price}")
        return price

    async def _fetch_coingecko_rest(self) -> float:
        """Fetch latest price from CoinGecko REST API."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized")

        url = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd"
        resp = await self._http_client.get(url)
        if resp.status_code >= 400:
            resp.raise_for_status()
        data = resp.json()
        price = float(data["the-open-network"]["usd"])
        if price <= 0:
            raise ValueError(f"Invalid CoinGecko price: {price}")
        return price

    async def _fetch_rest_fallback(self) -> float:
        """Execute REST fallback across available REST endpoints with deduplication."""
        cache_key = "ton_rest_fallback"
        cached_price = await self._rest_cache.get(cache_key)
        if cached_price is not None:
            logger.debug("Returning cached REST fallback price: %.4f", cached_price)
            return cached_price

        logger.info("Executing REST fallback for %s...", self.symbol_pair)
        price: Optional[float] = None
        source = "REST"

        # Try Binance REST first (highest liquidity and sub-second updates)
        try:
            price = await self._fetch_binance_rest()
            source = "Binance (REST)"
            logger.info("REST fallback succeeded via Binance: %.4f", price)
        except Exception as e:
            logger.warning("Binance REST fallback failed (%s). Trying CoinGecko fallback...", e)

        # If Binance fails, try CoinGecko REST
        if price is None:
            try:
                price = await self._fetch_coingecko_rest()
                source = "CoinGecko (REST)"
                logger.info("REST fallback succeeded via CoinGecko: %.4f", price)
            except Exception as e:
                logger.error("CoinGecko REST fallback failed (%s)", e)

        if price is None:
            raise RuntimeError("All crypto REST fallback endpoints failed")

        now_utc = datetime.now(timezone.utc)
        async with self._lock:
            self._latest_price = price
            self._latest_timestamp = now_utc
            self._latest_source = source
            self._feed_type = "REST Fallback"

        await self._rest_cache.set(cache_key, price, ttl_seconds=2.0)
        return price

    async def get_latest_price(
        self,
        force_rest: bool = False,
    ) -> tuple[Optional[float], Optional[datetime], str, str]:
        """Retrieve the latest TON/USDT price.
        
        Returns:
            tuple of (price, timestamp_utc, source_name, feed_type)
        """
        now = datetime.now(timezone.utc)

        # Check if in-memory WebSocket price is active and fresh
        async with self._lock:
            cached_price = self._latest_price
            cached_ts = self._latest_timestamp
            cached_source = self._latest_source
            feed_type = self._feed_type

        is_fresh = False
        if cached_price is not None and cached_ts is not None:
            age = (now - cached_ts).total_seconds()
            if age <= self.stale_threshold_seconds:
                is_fresh = True

        # If WebSocket is connected, fresh, and not force_rest, return immediately
        if self._ws_client.is_connected and is_fresh and not force_rest:
            return cached_price, cached_ts, cached_source, feed_type

        # If force_rest OR WS disconnected OR data is stale, trigger REST fallback
        logger.info(
            "WebSocket condition not met (connected=%s, fresh=%s, force=%s). Triggering REST fallback...",
            self._ws_client.is_connected,
            is_fresh,
            force_rest,
        )

        if force_rest:
            await self._rest_cache.invalidate("ton_rest_fallback")

        try:
            fallback_price = await self._fetch_rest_fallback()
            async with self._lock:
                return self._latest_price, self._latest_timestamp, self._latest_source, self._feed_type
        except Exception as e:
            logger.error("REST fallback execution failed: %s", e)
            # Return last known values even if stale, rather than None, so caller can evaluate freshness
            async with self._lock:
                return self._latest_price, self._latest_timestamp, self._latest_source, "Unavailable"
