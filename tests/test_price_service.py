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


def test_price_service_currency_conversions():
    """Verify mathematical accuracy of conversions across all assets."""
    service = PriceService()

    snapshot = PriceSnapshot(
        ton_usdt=2.0,      # 1 TON = $2.00
        usd_inr=100.0,     # $1 = ₹100
        ton_inr=200.0,     # 1 TON = ₹200
        ton_gram=2000.0,   # 1 TON = 2000 GRAM
        ton_stars=150.0,   # 1 TON = 150 Stars
    )

    # 1. Convert 10 TON
    res_ton = service.convert_currency(10.0, "TON", snapshot)
    assert res_ton["TON"] == 10.0
    assert res_ton["USDT"] == 20.0
    assert res_ton["INR"] == 2000.0
    assert res_ton["STARS"] == 1500.0
    assert "GRAM" not in res_ton

    # 2. Convert 100 INR -> 0.5 TON
    res_inr = service.convert_currency(100.0, "INR", snapshot)
    assert res_inr["TON"] == 0.5
    assert res_inr["USDT"] == 1.0
    assert res_inr["STARS"] == 75.0
    assert "GRAM" not in res_inr

    # 3. Convert 10 USDT -> 5 TON
    res_usdt = service.convert_currency(10.0, "USDT", snapshot)
    assert res_usdt["TON"] == 5.0
    assert res_usdt["INR"] == 1000.0
    assert res_usdt["STARS"] == 750.0
    assert "GRAM" not in res_usdt

    # 4. GRAM is no longer an accepted conversion input
    res_gram = service.convert_currency(1000.0, "GRAM", snapshot)
    assert res_gram == {"TON": None, "USDT": None, "INR": None, "STARS": None}

    # 5. Convert 150 STARS -> 1 TON
    res_stars = service.convert_currency(150.0, "STARS", snapshot)
    assert res_stars["TON"] == 1.0
    assert res_stars["USDT"] == 2.0
    assert res_stars["INR"] == 200.0
    assert "GRAM" not in res_stars

    # 6. Missing rates handled safely
    empty_snapshot = PriceSnapshot()
    res_empty = service.convert_currency(10.0, "INR", empty_snapshot)
    assert res_empty["TON"] is None
    assert res_empty["USDT"] is None
