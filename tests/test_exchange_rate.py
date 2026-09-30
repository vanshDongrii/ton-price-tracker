"""Unit tests for ExchangeRateService."""

from datetime import datetime, timezone
import httpx
import pytest

from src.services.exchange_rate import ExchangeRateService


@pytest.mark.asyncio
async def test_exchangerate_api_success(monkeypatch):
    """Verify parsing of ExchangeRate-API response."""
    service = ExchangeRateService(provider="exchangerate-api", cache_ttl_seconds=60)

    mock_response = httpx.Response(
        200,
        json={
            "result": "success",
            "time_last_update_unix": 1727690000,
            "rates": {"INR": 88.50},
        },
    )

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            return mock_response
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_usd_inr_rate(force_refresh=True)
    assert rate == 88.50
    assert ts is not None
    assert src == "ExchangeRate-API"


@pytest.mark.asyncio
async def test_frankfurter_fallback(monkeypatch):
    """Verify fallback to Frankfurter when ExchangeRate-API fails."""
    service = ExchangeRateService(provider="exchangerate-api", cache_ttl_seconds=60)

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            if "open.er-api.com" in url:
                raise httpx.ConnectTimeout("Connection timeout")
            if "frankfurter.app" in url:
                return httpx.Response(200, json={"rates": {"INR": 88.75}})
            raise ValueError("Unknown URL")
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_usd_inr_rate(force_refresh=True)
    assert rate == 88.75
    assert src == "Frankfurter (ECB)"


@pytest.mark.asyncio
async def test_all_fx_providers_fail():
    """Verify clean graceful return when all FX providers fail."""
    service = ExchangeRateService(provider="exchangerate-api", cache_ttl_seconds=60)

    class MockFailingClient:
        is_closed = False
        async def get(self, url, **kwargs):
            raise httpx.RequestError("Network error")
        async def aclose(self):
            pass

    service._http_client = MockFailingClient()

    rate, ts, src = await service.get_usd_inr_rate(force_refresh=True)
    assert rate is None
    assert ts is None
    assert src == "Unavailable"


@pytest.mark.asyncio
async def test_fx_cache_deduplication():
    """Verify that within cache TTL, HTTP client is not called again."""
    service = ExchangeRateService(provider="exchangerate-api", cache_ttl_seconds=300)

    call_count = 0

    class MockCountingClient:
        is_closed = False
        async def get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"rates": {"INR": 88.50}})
        async def aclose(self):
            pass

    service._http_client = MockCountingClient()

    # Call 1
    r1, _, _ = await service.get_usd_inr_rate(force_refresh=False)
    assert r1 == 88.50
    assert call_count == 1

    # Call 2 (cached)
    r2, _, _ = await service.get_usd_inr_rate(force_refresh=False)
    assert r2 == 88.50
    assert call_count == 1  # No extra network call!

    # Call 3 (force refresh)
    r3, _, _ = await service.get_usd_inr_rate(force_refresh=True)
    assert r3 == 88.50
    assert call_count == 2
