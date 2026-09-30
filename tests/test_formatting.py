"""Unit tests for currency and timestamp formatting."""

from datetime import datetime, timezone
import pytest

from src.bot.formatters import (
    format_inr,
    format_stars,
    format_timestamp_full,
    format_timestamp_short,
    format_usdt,
)
from src.models.price_snapshot import Freshness, PriceSnapshot


def test_format_usdt():
    """Verify USDT precision is 4 decimal places."""
    assert format_usdt(2.18456) == "$2.1846"
    assert format_usdt(2.1) == "$2.1000"
    assert format_usdt(0.0) == "$0.0000"
    assert format_usdt(None) == "Unavailable"


def test_format_inr():
    """Verify Indian numbering format (lakhs, crores grouping)."""
    assert format_inr(193.42) == "₹193.42"
    assert format_inr(999.99) == "₹999.99"
    assert format_inr(1000.0) == "₹1,000.00"
    assert format_inr(12345.67) == "₹12,345.67"
    assert format_inr(123456.78) == "₹1,23,456.78"
    assert format_inr(10000000.00) == "₹1,00,00,000.00"
    assert format_inr(None) == "Unavailable"


def test_format_stars():
    """Verify Stars formatting adheres to honesty rules."""
    assert format_stars(25.5) == "25.50 Stars"
    assert format_stars(None) == "Rate unavailable"


def test_format_timestamps():
    """Verify conversion from UTC to Asia/Kolkata (IST)."""
    utc_dt = datetime(2026, 9, 30, 9, 5, 21, tzinfo=timezone.utc)
    # 09:05:21 UTC + 05:30 = 14:35:21 IST (02:35:21 PM IST)
    full = format_timestamp_full(utc_dt)
    assert "30 Sep 2026, 02:35:21 PM IST" in full

    short = format_timestamp_short(utc_dt)
    assert short == "02:35:21 PM IST"

    assert format_timestamp_full(None) == "N/A"
    assert format_timestamp_short(None) == "N/A"


def test_freshness_badges():
    """Verify badges and short labels."""
    assert Freshness.LIVE.badge == "🟢 Live market data"
    assert Freshness.DELAYED.badge == "🟡 Data delayed"
    assert Freshness.UNAVAILABLE.badge == "🔴 Price unavailable"

    assert Freshness.LIVE.short_label == "🟢 LIVE"
    assert Freshness.DELAYED.short_label == "🟡 DELAYED"
    assert Freshness.UNAVAILABLE.short_label == "🔴 UNAVAILABLE"


def test_format_current_price_message_delayed_fx():
    """Verify that when FX is stale, INR displays delayed note."""
    from datetime import timedelta
    from src.bot.messages import format_current_price_message

    now_utc = datetime.now(timezone.utc)
    # TON is fresh (0s old), but FX is 30 hours old (> 24h threshold)
    stale_fx_ts = now_utc - timedelta(hours=30)

    snapshot = PriceSnapshot(
        ton_usdt=2.5000,
        usd_inr=90.00,
        ton_inr=225.00,
        ton_stars=None,
        ton_usdt_timestamp=now_utc,
        usd_inr_timestamp=stale_fx_ts,
        ton_inr_timestamp=stale_fx_ts,
        source="Whitebit (WS) + ExchangeRate-API",
        feed_type="WebSocket",
    )

    msg = format_current_price_message(snapshot, stale_after_seconds=15)
    assert "🇺🇸 *1 TON = $2.5000 USDT*" in msg
    assert "🇮🇳 *1 TON ≈ ₹225.00* _(delayed FX)_" in msg
    assert "⭐ *Stars: Rate unavailable*" in msg


def test_format_current_price_message_all_unavailable():
    """Verify format when data is completely unavailable."""
    from src.bot.messages import format_current_price_message

    snapshot = PriceSnapshot(
        ton_usdt=None,
        usd_inr=None,
        ton_inr=None,
        ton_stars=None,
        source="Unavailable",
        feed_type="None",
    )

    msg = format_current_price_message(snapshot, stale_after_seconds=15)
    assert "🇺🇸 *USDT: Unavailable*" in msg
    assert "🇮🇳 *INR: Unavailable*" in msg
    assert "⭐ *Stars: Rate unavailable*" in msg
    assert "🔴 Price unavailable" in msg

