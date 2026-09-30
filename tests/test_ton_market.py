"""Unit tests for TONMarketService: WebSocket prioritization and automatic REST fallback."""

import asyncio
from datetime import datetime, timedelta, timezone
import httpx
import pytest

from src.services.ton_market import TONMarketService


@pytest.mark.asyncio
async def test_uses_fresh_websocket_price_directly():
    """When WebSocket price is present and fresh, REST fallback is not called."""
    service = TONMarketService(provider="whitebit", stale_threshold_seconds=15)

    now_utc = datetime.now(timezone.utc)
    service._latest_price = 2.1845
    service._latest_timestamp = now_utc
    service._latest_source = "Whitebit (WS)"
    service._feed_type = "WebSocket"
    # Mock ws client as connected
    service._ws_client._connected = True

    rest_called = False

    async def mock_fallback():
        nonlocal rest_called
        rest_called = True
        return 999.0

    service._fetch_rest_fallback = mock_fallback

    price, ts, src, feed_type = await service.get_latest_price(force_rest=False)
    assert price == 2.1845
    assert src == "Whitebit (WS)"
    assert feed_type == "WebSocket"
    assert rest_called is False


@pytest.mark.asyncio
async def test_falls_back_to_rest_when_ws_disconnected():
    """When WebSocket is disconnected, REST fallback is automatically invoked."""
    service = TONMarketService(provider="whitebit", stale_threshold_seconds=15)
    service._ws_client._connected = False

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            return httpx.Response(200, json={"symbol": "TONUSDT", "price": "1.9500"})
        async def aclose(self):
            pass

    service._http_client = MockClient()

    price, ts, src, feed_type = await service.get_latest_price(force_rest=False)
    assert price == 1.9500
    assert "Binance (REST)" in src
    assert feed_type == "REST Fallback"


@pytest.mark.asyncio
async def test_falls_back_to_rest_when_ws_price_stale():
    """When in-memory price is older than stale threshold, triggers REST fallback."""
    service = TONMarketService(provider="whitebit", stale_threshold_seconds=15)
    # Price is 30 seconds old
    service._latest_price = 2.0000
    service._latest_timestamp = datetime.now(timezone.utc) - timedelta(seconds=30)
    service._latest_source = "Whitebit (WS)"
    service._ws_client._connected = True

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            return httpx.Response(200, json={"symbol": "TONUSDT", "price": "2.0500"})
        async def aclose(self):
            pass

    service._http_client = MockClient()

    price, ts, src, feed_type = await service.get_latest_price(force_rest=False)
    assert price == 2.0500
    assert "Binance (REST)" in src


@pytest.mark.asyncio
async def test_coingecko_secondary_rest_fallback():
    """When Binance REST fails, CoinGecko REST fallback is invoked."""
    service = TONMarketService(provider="whitebit", stale_threshold_seconds=15)
    service._ws_client._connected = False

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            if "binance.com" in url:
                raise httpx.ConnectTimeout("Binance timeout")
            if "coingecko.com" in url:
                return httpx.Response(200, json={"the-open-network": {"usd": 1.98}})
            raise ValueError("Unknown URL")
        async def aclose(self):
            pass

    service._http_client = MockClient()

    price, ts, src, feed_type = await service.get_latest_price(force_rest=False)
    assert price == 1.98
    assert src == "CoinGecko (REST)"


@pytest.mark.asyncio
async def test_rest_fallback_deduplication():
    """Multiple parallel requests during REST fallback do not duplicate external API calls."""
    service = TONMarketService(provider="whitebit", stale_threshold_seconds=15)
    service._ws_client._connected = False

    call_count = 0

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"symbol": "TONUSDT", "price": "1.9900"})
        async def aclose(self):
            pass

    service._http_client = MockClient()

    # Call 3 times rapidly
    res = await asyncio.gather(
        service.get_latest_price(),
        service.get_latest_price(),
        service.get_latest_price(),
    )
    for p, _, _, _ in res:
        assert p == 1.9900

    # Thanks to short TTL cache on REST fallback, only 1 actual HTTP call was made
    assert call_count == 1
