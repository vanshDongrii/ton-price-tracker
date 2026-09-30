"""High-level price service orchestrating crypto market feeds, FX rates, and Stars rates."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from src.config import Settings, get_settings
from src.models.price_snapshot import PriceSnapshot
from src.services.exchange_rate import ExchangeRateService
from src.services.stars_rate import StarsRateService
from src.services.ton_market import TONMarketService

logger = logging.getLogger(__name__)


class PriceService:
    """Orchestrates market data providers to deliver unified, real-time PriceSnapshots."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

        self.market_service = TONMarketService(
            provider=self.settings.crypto_api_provider,
            symbol_pair=self.settings.ton_usdt_symbol,
            stale_threshold_seconds=self.settings.price_stale_after_seconds,
            api_timeout_seconds=self.settings.api_timeout_seconds,
        )

        self.fx_service = ExchangeRateService(
            provider=self.settings.fx_api_provider,
            api_key=self.settings.fx_api_key,
            cache_ttl_seconds=self.settings.fx_cache_ttl_seconds,
            api_timeout_seconds=self.settings.api_timeout_seconds,
        )

        self.stars_service = StarsRateService(
            source=self.settings.stars_rate_source,
            api_key=self.settings.stars_rate_api_key,
            custom_api_url=self.settings.stars_custom_api_url,
            api_timeout_seconds=self.settings.api_timeout_seconds,
        )

        self._running = False
        self._last_snapshot: Optional[PriceSnapshot] = None
        self._lock = asyncio.Lock()

    @property
    def is_ws_connected(self) -> bool:
        """Return True if market WebSocket feed is connected."""
        return self.market_service.is_ws_connected

    async def start(self) -> None:
        """Start underlying services and initialize feeds."""
        if self._running:
            return
        self._running = True
        logger.info("Initializing PriceService...")
        await self.market_service.start()
        # Pre-fetch FX rate
        try:
            await self.fx_service.get_usd_inr_rate()
        except Exception as e:
            logger.warning("Pre-fetching FX rate failed: %s", e)

    async def stop(self) -> None:
        """Gracefully stop all underlying services."""
        logger.info("Stopping PriceService...")
        self._running = False
        await self.market_service.stop()
        await self.fx_service.aclose()
        await self.stars_service.aclose()

    async def get_snapshot(self, force_refresh: bool = False) -> PriceSnapshot:
        """Generate a complete, up-to-date PriceSnapshot across all currencies.
        
        Args:
            force_refresh: If True, forces live REST checks even if cached/streaming.
        """
        # Fetch TON/USDT, USD/INR, and Stars in parallel
        ton_task = self.market_service.get_latest_price(force_rest=force_refresh)
        fx_task = self.fx_service.get_usd_inr_rate(force_refresh=force_refresh)
        stars_task = self.stars_service.get_stars_rate(force_refresh=force_refresh)

        results = await asyncio.gather(ton_task, fx_task, stars_task, return_exceptions=True)

        # Parse TON market data
        ton_res = results[0]
        if isinstance(ton_res, Exception) or not isinstance(ton_res, tuple):
            logger.error("Error retrieving TON market data: %s", ton_res)
            ton_usdt, ton_usdt_ts, ton_src, feed_type = None, None, "Unavailable", "Unavailable"
        else:
            ton_usdt, ton_usdt_ts, ton_src, feed_type = ton_res

        # Parse FX data
        fx_res = results[1]
        if isinstance(fx_res, Exception) or not isinstance(fx_res, tuple):
            logger.error("Error retrieving FX rate: %s", fx_res)
            usd_inr, usd_inr_ts, fx_src = None, None, "Unavailable"
        else:
            usd_inr, usd_inr_ts, fx_src = fx_res

        # Parse Stars data
        stars_res = results[2]
        if isinstance(stars_res, Exception) or not isinstance(stars_res, tuple):
            logger.error("Error retrieving Stars rate: %s", stars_res)
            ton_stars, stars_ts, stars_src = None, None, "Unavailable"
        else:
            ton_stars, stars_ts, stars_src = stars_res

        # Calculate TON/INR
        ton_inr: Optional[float] = None
        ton_inr_ts: Optional[datetime] = None
        if ton_usdt is not None and usd_inr is not None:
            ton_inr = round(ton_usdt * usd_inr, 4)
            # Freshness of calculated INR is bounded by the older of the two components
            ton_inr_ts = min(ton_usdt_ts, usd_inr_ts) if (ton_usdt_ts and usd_inr_ts) else (ton_usdt_ts or usd_inr_ts)

        # Compose source label
        source_label = f"{ton_src} + {fx_src}"

        snapshot = PriceSnapshot(
            ton_usdt=ton_usdt,
            usd_inr=usd_inr,
            ton_inr=ton_inr,
            ton_stars=ton_stars,
            ton_usdt_timestamp=ton_usdt_ts,
            usd_inr_timestamp=usd_inr_ts,
            ton_inr_timestamp=ton_inr_ts,
            stars_timestamp=stars_ts,
            source=source_label,
            feed_type=feed_type,
        )

        async with self._lock:
            self._last_snapshot = snapshot

        return snapshot
