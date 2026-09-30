"""Text messages and templates for the TON Price Tracker Telegram bot."""

from datetime import datetime, timezone
from typing import Optional

from src.bot.formatters import (
    format_inr,
    format_stars,
    format_timestamp_full,
    format_timestamp_short,
    format_usdt,
)
from src.models.price_snapshot import Freshness, PriceSnapshot


def get_welcome_message() -> str:
    """Return the welcome text for the /start command."""
    return (
        "💎 *TON Price Tracker*\n\n"
        "Get the latest Toncoin value in USDT, INR and Telegram Stars.\n\n"
        "Choose an option below:"
    )


def format_current_price_message(
    snapshot: PriceSnapshot,
    stale_after_seconds: int = 15,
) -> str:
    """Format the full current price screen message."""
    ton_freshness = snapshot.get_ton_usdt_freshness(stale_after_seconds)
    inr_freshness = snapshot.get_ton_inr_freshness(stale_after_seconds)

    # USDT row
    if snapshot.ton_usdt is not None:
        usdt_str = f"🇺🇸 *1 TON = {format_usdt(snapshot.ton_usdt)} USDT*"
    else:
        usdt_str = "🇺🇸 *USDT: Unavailable*"

    # INR row
    if snapshot.ton_inr is not None:
        inr_note = " _(delayed FX)_" if inr_freshness == Freshness.DELAYED else ""
        inr_str = f"🇮🇳 *1 TON ≈ {format_inr(snapshot.ton_inr)}*{inr_note}"
    else:
        inr_str = "🇮🇳 *INR: Unavailable*"

    # Stars row
    if snapshot.ton_stars is not None:
        stars_str = f"⭐ *1 TON = {format_stars(snapshot.ton_stars)}*"
    else:
        stars_str = "⭐ *Stars: Rate unavailable*"

    # Freshness badge
    overall_freshness = snapshot.get_overall_freshness(stale_after_seconds)
    badge = overall_freshness.badge

    # Updated timestamp
    ts_str = format_timestamp_full(snapshot.latest_timestamp)

    # Source info
    source_str = f"📊 Source: {snapshot.source} ({snapshot.feed_type})"

    lines = [
        "💎 *TON Current Price*",
        "",
        "━━━━━━━━━━━━━━━━━━",
        "",
        usdt_str,
        "",
        inr_str,
        "",
        stars_str,
        "",
        "━━━━━━━━━━━━━━━━━━",
        "",
        badge,
        f"🕐 Updated: {ts_str}",
        "",
        source_str,
    ]
    return "\n".join(lines)


def format_live_price_message(
    snapshot: PriceSnapshot,
    stale_after_seconds: int = 15,
) -> str:
    """Format the compact live price screen message."""
    # USDT row
    if snapshot.ton_usdt is not None:
        usdt_val = format_usdt(snapshot.ton_usdt)
    else:
        usdt_val = "Unavailable"

    # INR row
    if snapshot.ton_inr is not None:
        inr_val = format_inr(snapshot.ton_inr)
    else:
        inr_val = "Unavailable"

    # Stars row
    if snapshot.ton_stars is not None:
        stars_val = f"{snapshot.ton_stars:.2f}"
    else:
        stars_val = "Rate unavailable"

    # Freshness label
    overall_freshness = snapshot.get_overall_freshness(stale_after_seconds)
    badge = overall_freshness.short_label

    ts_str = format_timestamp_short(snapshot.latest_timestamp)

    lines = [
        "💎 *TON Live Price*",
        "",
        f"🇺🇸 USDT: {usdt_val}",
        f"🇮🇳 INR: {inr_val}",
        f"⭐ Stars: {stars_val}",
        "",
        badge,
        "",
        f"Updated: {ts_str}",
    ]
    return "\n".join(lines)


def get_help_message() -> str:
    """Return the /help information message."""
    return (
        "📖 *TON Price Tracker — User Guide*\n\n"
        "Here are the commands you can use:\n\n"
        "• /start — Open the main welcome menu\n"
        "• /price — Display the latest TON market price\n"
        "• /refresh — Request an immediate live market refresh\n"
        "• /help — Show this help manual\n"
        "• /about — Details about data sources, architecture & Stars\n\n"
        "📡 *Live Price Mode:*\n"
        "Press 'Live Price' to activate continuous real-time updates. "
        "The message edits in place without sending notification spam. "
        "Press 'Stop Live Updates' at any time to return to normal mode.\n\n"
        "🟢 *Data Freshness:*\n"
        "• 🟢 Live — Ticker updated within 15 seconds\n"
        "• 🟡 Delayed — Network latency or provider delay\n"
        "• 🔴 Unavailable — External market feed offline"
    )


def get_about_message() -> str:
    """Return the /about information message."""
    return (
        "ℹ️ *About TON Price Tracker*\n\n"
        "A production-grade Telegram bot providing verified, real-time market data "
        "for The Open Network (Toncoin).\n\n"
        "🏗 *Architecture & Data Pipeline:*\n"
        "• *Live Crypto Feed:* High-frequency WebSocket ticker streaming live trades "
        "directly into memory.\n"
        "• *Automatic REST Fallback:* If WebSocket disconnects or stalls, automatically "
        "falls back to REST endpoints with sub-second resilience.\n"
        "• *Live Currency Conversion:* USD/INR exchange rates sourced from live forex APIs "
        "with timestamp freshness tracking.\n\n"
        "⭐ *About Telegram Stars:*\n"
        "Telegram Stars are an in-app Telegram currency with fixed tiered package pricing. "
        "Unlike Toncoin, Stars do not have a free-floating open cryptocurrency exchange pair. "
        "In strict accordance with data accuracy standards, this bot *never* fabricates or guesses "
        "rates and displays 'Rate unavailable' unless an authenticated live conversion source is linked.\n\n"
        "🛡 *Security & Integrity:*\n"
        "Zero dummy data. Zero fabricated rates. Built with Python 3.11+, python-telegram-bot, "
        "httpx, and websockets."
    )
