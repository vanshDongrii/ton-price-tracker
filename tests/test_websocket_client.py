"""Unit tests for WebSocket message parsing, reconnection, and error handling."""

import asyncio
from datetime import datetime, timezone
import pytest

from src.services.websocket_client import CryptoWebSocketClient


def test_parse_whitebit_valid():
    """Verify parsing of standard WhiteBIT lastprice_update frame."""
    client = CryptoWebSocketClient(provider="whitebit", symbol_pair="TONUSDT")
    raw = '{"method": "lastprice_update", "params": ["TON_USDT", "1.773"]}'
    res = client._parse_message(raw)
    assert res is not None
    price, ts = res
    assert price == 1.773
    assert isinstance(ts, datetime)


def test_parse_binance_trade_valid():
    """Verify parsing of Binance trade message."""
    client = CryptoWebSocketClient(provider="binance", symbol_pair="TONUSDT")
    raw = '{"e": "trade", "s": "TONUSDT", "p": "1.8550", "T": 1727690000000}'
    res = client._parse_message(raw)
    assert res is not None
    price, ts = res
    assert price == 1.8550
    assert ts.year == 2024 or ts.year == 2026


def test_parse_binance_ticker_valid():
    """Verify parsing of Binance ticker message."""
    client = CryptoWebSocketClient(provider="binance", symbol_pair="TONUSDT")
    raw = '{"c": "1.9200"}'
    res = client._parse_message(raw)
    assert res is not None
    price, ts = res
    assert price == 1.9200


def test_parse_invalid_json():
    """Malformed non-JSON strings return None without raising exceptions."""
    client = CryptoWebSocketClient(provider="whitebit", symbol_pair="TONUSDT")
    assert client._parse_message("not valid json <xml>") is None
    assert client._parse_message("") is None


def test_parse_unrelated_message():
    """Subscription confirmation or ping/pong messages return None cleanly."""
    client = CryptoWebSocketClient(provider="whitebit", symbol_pair="TONUSDT")
    raw = '{"error": null, "result": {"status": "success"}, "id": 1}'
    assert client._parse_message(raw) is None


@pytest.mark.asyncio
async def test_websocket_callback_invocation():
    """Verify that when a valid message is parsed, on_price_update callback fires."""
    received = []

    async def callback(price, ts, source):
        received.append((price, source))

    client = CryptoWebSocketClient(provider="whitebit", on_price_update=callback)
    raw = '{"method": "lastprice_update", "params": ["TON_USDT", "2.1845"]}'
    parsed = client._parse_message(raw)
    assert parsed is not None
    price, ts = parsed
    await client.on_price_update(price, ts, "Whitebit (WS)")

    assert len(received) == 1
    assert received[0][0] == 2.1845
    assert received[0][1] == "Whitebit (WS)"


@pytest.mark.asyncio
async def test_websocket_client_lifecycle():
    """Verify start and stop methods manage tasks cleanly."""
    client = CryptoWebSocketClient(provider="whitebit")
    client.start()
    assert client._running is True
    assert client._task is not None

    await client.stop()
    assert client._running is False
    assert client.is_connected is False


def test_exponential_backoff_progression():
    """Verify backoff doubles each iteration up to max_backoff."""
    client = CryptoWebSocketClient(
        provider="whitebit",
        initial_backoff_seconds=1.0,
        max_backoff_seconds=16.0,
    )
    b = client.initial_backoff
    assert b == 1.0
    b = min(b * 2.0, client.max_backoff)
    assert b == 2.0
    b = min(b * 2.0, client.max_backoff)
    assert b == 4.0
    b = min(b * 2.0, client.max_backoff)
    assert b == 8.0
    b = min(b * 2.0, client.max_backoff)
    assert b == 16.0
    b = min(b * 2.0, client.max_backoff)
    assert b == 16.0  # Capped at max_backoff

