"""High-level price service orchestrating crypto market feeds, FX rates, and Stars rates."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from src.config import Settings, get_settings
from src.models.price_snapshot import PriceSnapshot
from src.services.exchange_rate import ExchangeRateService
from src.services.gram_rate import GramRateService
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

        self.gram_service = GramRateService(
            contract_address=self.settings.gram_contract_address,
            cache_ttl_seconds=self.settings.gram_cache_ttl_seconds,
            api_timeout_seconds=self.settings.api_timeout_seconds,
        )

        self.stars_service = StarsRateService(
            source=self.settings.stars_rate_source,
            api_key=self.settings.stars_rate_api_key,
            custom_api_url=self.settings.stars_custom_api_url,
            stars_usd_rate=self.settings.stars_usd_rate,
            stars_per_ton=self.settings.stars_per_ton,
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
        await self.gram_service.aclose()
        await self.stars_service.aclose()

    async def get_snapshot(self, force_refresh: bool = False) -> PriceSnapshot:
        """Generate a complete, up-to-date PriceSnapshot across all currencies.

        Args:
            force_refresh: If True, forces live REST checks even if cached/streaming.
        """
        # Fetch TON/USDT and USD/INR in parallel
        ton_task = self.market_service.get_latest_price(force_rest=force_refresh)
        fx_task = self.fx_service.get_usd_inr_rate(force_refresh=force_refresh)

        ton_res, fx_res = await asyncio.gather(ton_task, fx_task, return_exceptions=True)

        # Parse TON market data
        if isinstance(ton_res, Exception) or not isinstance(ton_res, tuple):
            logger.error("Error retrieving TON market data: %s", ton_res)
            ton_usdt, ton_usdt_ts, ton_src, feed_type = None, None, "Unavailable", "Unavailable"
        else:
            ton_usdt, ton_usdt_ts, ton_src, feed_type = ton_res

        # Parse FX data
        if isinstance(fx_res, Exception) or not isinstance(fx_res, tuple):
            logger.error("Error retrieving FX rate: %s", fx_res)
            usd_inr, usd_inr_ts, fx_src = None, None, "Unavailable"
        else:
            usd_inr, usd_inr_ts, fx_src = fx_res

        # Fetch GRAM and Stars data with ton_usdt context
        async def fetch_gram():
            if hasattr(self, "gram_service") and self.gram_service is not None:
                try:
                    return await self.gram_service.get_gram_rate(ton_usdt=ton_usdt, force_refresh=force_refresh)
                except Exception as ex:
                    logger.error("Error retrieving GRAM rate: %s", ex)
            return None, None, "Unavailable"

        async def fetch_stars():
            if hasattr(self, "stars_service") and self.stars_service is not None:
                try:
                    return await self.stars_service.get_stars_rate(ton_usdt=ton_usdt, force_refresh=force_refresh)
                except TypeError:
                    # In case of mock in tests without ton_usdt parameter
                    return await self.stars_service.get_stars_rate(force_refresh=force_refresh)
                except Exception as ex:
                    logger.error("Error retrieving Stars rate: %s", ex)
            return None, None, "Unavailable"

        gram_res, stars_res = await asyncio.gather(fetch_gram(), fetch_stars(), return_exceptions=True)

        # Parse GRAM data
        if isinstance(gram_res, Exception) or not isinstance(gram_res, tuple):
            logger.error("Error parsing GRAM rate: %s", gram_res)
            ton_gram, gram_ts, gram_src = None, None, "Unavailable"
        else:
            ton_gram, gram_ts, gram_src = gram_res

        # Parse Stars data
        if isinstance(stars_res, Exception) or not isinstance(stars_res, tuple):
            logger.error("Error parsing Stars rate: %s", stars_res)
            ton_stars, stars_ts, stars_src = None, None, "Unavailable"
        else:
            ton_stars, stars_ts, stars_src = stars_res

        # Calculate TON/INR
        ton_inr: Optional[float] = None
        ton_inr_ts: Optional[datetime] = None
        if ton_usdt is not None and usd_inr is not None:
            ton_inr = round(ton_usdt * usd_inr, 4)
            ton_inr_ts = min(ton_usdt_ts, usd_inr_ts) if (ton_usdt_ts and usd_inr_ts) else (ton_usdt_ts or usd_inr_ts)

        # Compose source label
        source_label = f"{ton_src} + {fx_src}"

        snapshot = PriceSnapshot(
            ton_usdt=ton_usdt,
            usd_inr=usd_inr,
            ton_inr=ton_inr,
            ton_gram=ton_gram,
            ton_stars=ton_stars,
            ton_usdt_timestamp=ton_usdt_ts,
            usd_inr_timestamp=usd_inr_ts,
            ton_inr_timestamp=ton_inr_ts,
            ton_gram_timestamp=gram_ts,
            stars_timestamp=stars_ts,
            source=source_label,
            feed_type=feed_type,
        )

        async with self._lock:
            self._last_snapshot = snapshot

        return snapshot

    def convert_currency(
        self,
        amount: float,
        from_asset: str,
        snapshot: PriceSnapshot,
    ) -> dict[str, Optional[float]]:
        """Calculate conversions for a given amount from from_asset across all supported assets.

        Supported assets: 'TON', 'USDT', 'INR', 'GRAM', 'STARS'.
        Returns dictionary of {asset: converted_amount_or_None}.
        """
        asset = from_asset.upper().strip()

        # Step 1: Normalize input to base TON amount
        ton_amount: Optional[float] = None

        if asset in ("TON", "TONCOIN"):
            ton_amount = amount
        elif asset in ("USDT", "USD"):
            if snapshot.ton_usdt and snapshot.ton_usdt > 0:
                ton_amount = amount / snapshot.ton_usdt
        elif asset == "INR":
            if snapshot.ton_inr and snapshot.ton_inr > 0:
                ton_amount = amount / snapshot.ton_inr
        elif asset in ("GRAM", "GRM"):
            if snapshot.ton_gram and snapshot.ton_gram > 0:
                ton_amount = amount / snapshot.ton_gram
        elif asset in ("STARS", "STAR", "TELEGRAM_STARS"):
            if snapshot.ton_stars and snapshot.ton_stars > 0:
                ton_amount = amount / snapshot.ton_stars

        if ton_amount is None:
            return {
                "TON": None,
                "USDT": None,
                "INR": None,
                "GRAM": None,
                "STARS": None,
            }

        # Step 2: Calculate target asset values from TON
        return {
            "TON": round(ton_amount, 4) if asset != "TON" else amount,
            "USDT": round(ton_amount * snapshot.ton_usdt, 4) if snapshot.ton_usdt else None,
            "INR": round(ton_amount * snapshot.ton_inr, 2) if snapshot.ton_inr else None,
            "GRAM": round(ton_amount * snapshot.ton_gram, 2) if snapshot.ton_gram else None,
            "STARS": round(ton_amount * snapshot.ton_stars, 2) if snapshot.ton_stars else None,
        }
