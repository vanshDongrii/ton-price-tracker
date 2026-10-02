"""Unit tests for currency and timestamp formatting."""

from datetime import datetime, timezone
import pytest

from src.bot.formatters import (
    format_gram,
    format_inr,
    format_stars,
    format_timestamp_full,
    format_timestamp_short,
    format_timestamp_utc,
    format_ton,
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
    assert format_stars(25.0) == "25 Stars"
    assert format_stars(25.5) == "26 Stars"
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


def test_format_gram():
    """Verify GRAM formatting."""
    assert format_gram(2082.75) == "2,082.75 GRAM"
    assert format_gram(None) == "Rate unavailable"


def test_format_ton():
    """Verify TON precision formatting."""
    assert format_ton(1.5491) == "1.5491 TON"
    assert format_ton(None) == "Unavailable"


def test_format_timestamp_utc():
    """Verify clean UTC timestamp string."""
    utc_dt = datetime(2026, 9, 30, 9, 5, 21, tzinfo=timezone.utc)
    assert format_timestamp_utc(utc_dt) == "09:05:21 UTC"
    assert format_timestamp_utc(None) == "N/A"


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
        ton_gram=2000.0,
        ton_stars=None,
        ton_usdt_timestamp=now_utc,
        usd_inr_timestamp=stale_fx_ts,
        ton_inr_timestamp=stale_fx_ts,
        source="Whitebit (WS) + ExchangeRate-API",
        feed_type="WebSocket",
    )

    msg = format_current_price_message(snapshot, stale_after_seconds=15)
    assert "1 TON = $2.5000 USDT" in msg
    assert "1 TON = ₹225.00 INR _(delayed FX)_" in msg
    assert "1 TON = 2,000.00 GRAM" in msg
    assert "1 TON = Telegram Stars: Rate unavailable" in msg


def test_format_current_price_message_all_unavailable():
    """Verify format when data is completely unavailable."""
    from src.bot.messages import format_current_price_message

    snapshot = PriceSnapshot(
        ton_usdt=None,
        usd_inr=None,
        ton_inr=None,
        ton_gram=None,
        ton_stars=None,
        source="Unavailable",
        feed_type="None",
    )

    msg = format_current_price_message(snapshot, stale_after_seconds=15)
    assert "1 TON = USDT: Unavailable" in msg
    assert "1 TON = INR: Unavailable" in msg
    assert "1 TON = GRAM: Unavailable" in msg
    assert "1 TON = Telegram Stars: Rate unavailable" in msg
    assert "🔴 Price unavailable" in msg


def test_format_conversion_message():
    """Verify conversion message markdown output."""
    from src.bot.messages import format_conversion_message

    conversions = {
        "TON": 10.0,
        "USDT": 15.49,
        "INR": 1492.50,
        "GRAM": 20827.50,
        "STARS": 1192.30,
    }

    msg = format_conversion_message(10.0, "TON", conversions)
    assert "💎 *10 TON*" in msg
    assert "≈ $15.4900 USDT" in msg
    assert "≈ ₹1,492.50 INR" in msg
    assert "≈ 20,827.50 GRAM" in msg
    assert "≈ 1,192 Stars" in msg

