"""Formatting utilities for currencies, Indian numbering system, and IST timestamps."""

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from src.models.price_snapshot import Freshness, PriceSnapshot

IST_TZ = ZoneInfo("Asia/Kolkata")


def format_inr(amount: Optional[float]) -> str:
    """Format float into Indian Rupee numbering format (e.g. ₹1,23,456.78).
    
    In the Indian numbering system:
    - Last 3 digits are grouped together.
    - Subsequent higher digits are grouped in pairs of two.
    """
    if amount is None:
        return "Unavailable"

    # Split into integer and decimal components
    rounded = f"{amount:.2f}"
    int_part, dec_part = rounded.split(".")

    is_negative = int_part.startswith("-")
    if is_negative:
        int_part = int_part[1:]

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        # Last 3 digits
        last_three = int_part[-3:]
        remaining = int_part[:-3]
        # Group remaining digits in pairs of two from right to left
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last_three

    sign = "-" if is_negative else ""
    return f"₹{sign}{formatted_int}.{dec_part}"


def format_usdt(amount: Optional[float]) -> str:
    """Format USDT with 4 decimal places precision (e.g. $2.1845)."""
    if amount is None:
        return "Unavailable"
    return f"${amount:.4f}"


def format_stars(amount: Optional[float]) -> str:
    """Format Telegram Stars as whole integer units or return 'Rate unavailable'."""
    if amount is None:
        return "Rate unavailable"
    return f"{int(round(amount)):,} Stars"


def format_gram(amount: Optional[float]) -> str:
    """Format GRAM token or return 'Rate unavailable'."""
    if amount is None:
        return "Rate unavailable"
    return f"{amount:,.2f} GRAM"


def format_ton(amount: Optional[float]) -> str:
    """Format TON amount with up to 4 decimal places."""
    if amount is None:
        return "Unavailable"
    return f"{amount:.4f} TON"


def format_timestamp_utc(dt: Optional[datetime]) -> str:
    """Format UTC datetime into clean HH:MM:SS UTC string."""
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%H:%M:%S UTC")


def format_timestamp_full(dt: Optional[datetime]) -> str:
    """Format UTC datetime into human-readable IST string.
    
    Example: '30 Sep 2026, 02:35:21 PM IST'
    """
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST_TZ)
    return ist_dt.strftime("%d %b %Y, %I:%M:%S %p IST")


def format_timestamp_short(dt: Optional[datetime]) -> str:
    """Format UTC datetime into short time IST string for live mode.
    
    Example: '02:35:21 PM IST'
    """
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST_TZ)
    return ist_dt.strftime("%I:%M:%S %p IST")
