"""Unit tests for GramRateService."""

import asyncio
import httpx
import pytest

from src.services.gram_rate import DEFAULT_GRAM_CONTRACT, GramRateService


@pytest.mark.asyncio
async def test_gram_rate_tonapi_success():
    """Verify TonAPI returns correct 1 TON = X GRAM rate."""
    service = GramRateService()

    # 1 GRAM = 0.0005 TON -> 1 TON = 2000 GRAM
    mock_payload = {
        "rates": {
            DEFAULT_GRAM_CONTRACT: {
                "prices": {
                    "TON": 0.0005,
                    "USD": 0.001,
                }
            }
        }
    }

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            return httpx.Response(200, json=mock_payload)
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_gram_rate(ton_usdt=2.0, force_refresh=True)
    assert rate == 2000.0
    assert ts is not None
    assert src == "TonAPI"


@pytest.mark.asyncio
async def test_gram_rate_stonfi_fallback():
    """Verify STON.fi fallback when TonAPI fails."""
    service = GramRateService()

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            if "tonapi.io" in str(url):
                return httpx.Response(500, text="Server Error")
            if "ston.fi" in str(url):
                # 1 GRAM = $0.001 USD. If TON = $2.0, 1 TON = 2.0 / 0.001 = 2000 GRAM
                return httpx.Response(200, json={
                    "asset": {
                        "dex_usd_price": 0.001,
                    }
                })
            return httpx.Response(404)

        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_gram_rate(ton_usdt=2.0, force_refresh=True)
    assert rate == 2000.0
    assert ts is not None
    assert "STON.fi" in src


@pytest.mark.asyncio
async def test_gram_rate_all_fail():
    """When all providers fail, return None honestly without fabricating."""
    service = GramRateService()

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            return httpx.Response(500, text="Server Error")
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate, ts, src = await service.get_gram_rate(ton_usdt=2.0, force_refresh=True)
    assert rate is None
    assert ts is None
    assert src == "Unavailable"


@pytest.mark.asyncio
async def test_gram_rate_caching():
    """Verify that cached rate avoids subsequent network calls."""
    service = GramRateService(cache_ttl_seconds=60)
    call_count = 0

    class MockClient:
        is_closed = False
        async def get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={
                "rates": {
                    DEFAULT_GRAM_CONTRACT: {
                        "prices": {"TON": 0.0004}
                    }
                }
            })
        async def aclose(self):
            pass

    service._http_client = MockClient()

    rate1, _, _ = await service.get_gram_rate(force_refresh=False)
    rate2, _, _ = await service.get_gram_rate(force_refresh=False)

    assert rate1 == 2500.0
    assert rate2 == 2500.0
    assert call_count == 1
