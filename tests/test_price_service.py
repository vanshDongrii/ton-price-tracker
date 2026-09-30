"""Unit tests for PriceService orchestration and PriceSnapshot calculation."""

from datetime import datetime, timedelta, timezone
import pytest

from src.models.price_snapshot import Freshness, PriceSnapshot
from src.services.price_service import PriceService


@pytest.mark.asyncio
async def test_price_service_snapshot_full_calculation():
    """Verify TON/INR multiplication and snapshot composition."""
    service = PriceService()

    now_utc = datetime.now(timezone.utc)

    # Mock market service
    async def mock_ton(force_rest=False):
        return 2.5000, now_utc, "Whitebit (WS)", "WebSocket"

    # Mock FX service
    async def mock_fx(force_refresh=False):
        return 88.00, now_utc, "ExchangeRate-API"

    # Mock Stars service (valid)
    async def mock_stars(force_refresh=False):
        return 125.0, now_utc, "Custom API"

    service.market_service.get_latest_price = mock_ton
    service.fx_service.get_usd_inr_rate = mock_fx
    service.stars_service.get_stars_rate = mock_stars

    snapshot = await service.get_snapshot()

    assert snapshot.ton_usdt == 2.5000
    assert snapshot.usd_inr == 88.00
    # 2.5 * 88.00 = 220.0
    assert snapshot.ton_inr == 220.00
    assert snapshot.ton_stars == 125.0
    assert snapshot.feed_type == "WebSocket"
    assert "Whitebit (WS)" in snapshot.source

    # Freshness
    assert snapshot.get_ton_usdt_freshness() == Freshness.LIVE
    assert snapshot.get_ton_inr_freshness() == Freshness.LIVE
    assert snapshot.get_overall_freshness() == Freshness.LIVE


@pytest.mark.asyncio
async def test_price_service_missing_fx_data():
    """When FX is unavailable, TON/USDT remains live and INR is marked Unavailable."""
    service = PriceService()
    now_utc = datetime.now(timezone.utc)

    async def mock_ton(force_rest=False):
        return 2.5000, now_utc, "Whitebit (WS)", "WebSocket"

    async def mock_fx(force_refresh=False):
        return None, None, "Unavailable"

    async def mock_stars(force_refresh=False):
        return None, None, "Unavailable"

    service.market_service.get_latest_price = mock_ton
    service.fx_service.get_usd_inr_rate = mock_fx
    service.stars_service.get_stars_rate = mock_stars

    snapshot = await service.get_snapshot()

    assert snapshot.ton_usdt == 2.5000
    assert snapshot.usd_inr is None
    assert snapshot.ton_inr is None
    assert snapshot.ton_stars is None

    assert snapshot.get_ton_usdt_freshness() == Freshness.LIVE
    assert snapshot.get_ton_inr_freshness() == Freshness.UNAVAILABLE
    assert snapshot.get_stars_freshness() == Freshness.UNAVAILABLE


@pytest.mark.asyncio
async def test_price_service_stale_data_detection():
    """Verify that data older than stale threshold is marked DELAYED."""
    service = PriceService()

    # Timestamp is 20 seconds old (> 15 seconds threshold)
    stale_ts = datetime.now(timezone.utc) - timedelta(seconds=20)

    async def mock_ton(force_rest=False):
        return 2.5000, stale_ts, "Whitebit (WS)", "WebSocket"

    async def mock_fx(force_refresh=False):
        return 88.00, stale_ts, "ExchangeRate-API"

    async def mock_stars(force_refresh=False):
        return None, None, "Unavailable"

    service.market_service.get_latest_price = mock_ton
    service.fx_service.get_usd_inr_rate = mock_fx
    service.stars_service.get_stars_rate = mock_stars

    snapshot = await service.get_snapshot()

    assert snapshot.get_ton_usdt_freshness(stale_after_seconds=15) == Freshness.DELAYED
    assert snapshot.get_ton_inr_freshness(stale_after_seconds=15) == Freshness.DELAYED
    assert snapshot.get_overall_freshness(stale_after_seconds=15) == Freshness.DELAYED
