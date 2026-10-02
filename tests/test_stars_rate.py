"""Unit tests for StarsRateService."""

import httpx
import pytest

from src.services.stars_rate import StarsRateService


@pytest.mark.asyncio
async def test_stars_rate_default_none():
    """Default source 'none' must return None honestly without fabrication."""
    service = StarsRateService(source="none")
    rate, ts, src = await service.get_stars_rate()
    assert rate is None
    assert ts is None
    assert src == "Unavailable"


@pytest.mark.asyncio
async def test_stars_rate_custom_valid():
    """Custom API returning valid Stars rate."""
    service = StarsRateService(
        source="custom",
        custom_api_url="https://api.example.com/stars",
    )

    class MockClient:
        is_closed = False
        async def get(self, url, headers=None):
            return httpx.Response(200, json={"ton_stars": 120.5})
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_stars_rate(force_refresh=True)
    assert rate == 120.5
    assert ts is not None
    assert src == "Custom API"


@pytest.mark.asyncio
async def test_stars_rate_custom_invalid_response():
    """Custom API returning malformed or missing data returns None."""
    service = StarsRateService(
        source="custom",
        custom_api_url="https://api.example.com/stars",
    )

    class MockClient:
        is_closed = False
        async def get(self, url, headers=None):
            return httpx.Response(200, json={"unexpected_field": "not_a_rate"})
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_stars_rate(force_refresh=True)
    assert rate is None
    assert ts is None


@pytest.mark.asyncio
async def test_stars_rate_custom_http_error():
    """Custom API returning 500 error returns None safely."""
    service = StarsRateService(
        source="custom",
        custom_api_url="https://api.example.com/stars",
    )

    class MockClient:
        is_closed = False
        async def get(self, url, headers=None):
            return httpx.Response(500, text="Internal Server Error")
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_stars_rate(force_refresh=True)
    assert rate is None
    assert ts is None


@pytest.mark.asyncio
async def test_stars_rate_telegram_official():
    """Verify official Telegram developer rate ($0.013/star) calculation."""
    service = StarsRateService(source="telegram_official", stars_usd_rate=0.013)
    # At TON = $1.55 USD, 1.55 / 0.013 = 119.23 Stars
    rate, ts, src = await service.get_stars_rate(ton_usdt=1.55)
    assert rate == 119.23
    assert ts is not None
    assert "Telegram Official" in src


@pytest.mark.asyncio
async def test_stars_rate_fragment_purchase():
    """Verify Fragment official purchase rate ($0.015/star) calculation."""
    service = StarsRateService(source="fragment", stars_usd_rate=0.015)
    # At TON = $1.50 USD, 1.50 / 0.015 = 100.0 Stars
    rate, ts, src = await service.get_stars_rate(ton_usdt=1.50)
    assert rate == 100.0
    assert ts is not None
    assert "Fragment" in src


@pytest.mark.asyncio
async def test_stars_rate_static_override():
    """Verify manual override via stars_per_ton."""
    service = StarsRateService(source="telegram_official", stars_per_ton=150.0)
    rate, ts, src = await service.get_stars_rate(ton_usdt=1.55)
    assert rate == 150.0
    assert src == "Configured Rate"
