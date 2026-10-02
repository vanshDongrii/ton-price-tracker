"""Text messages and templates for the TON Price Live Telegram bot."""

from datetime import datetime, timezone
from typing import Optional

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


def get_welcome_message() -> str:
    """Return the welcome text for the /start command."""
    return (
        "💎 *Welcome to TON Price Live!*\n\n"
        "Get the latest TON value in:\n\n"
        "💵 USDT\n"
        "🇮🇳 INR\n"
        "🪙 GRAM\n"
        "⭐ Telegram Stars\n\n"
        "Choose an option below or type an amount (e.g. `10 TON` or `100 INR`):"
    )


def format_current_price_message(
    snapshot: PriceSnapshot,
    stale_after_seconds: int = 15,
) -> str:
    """Format the clean price dashboard message."""
    # USDT row
    if snapshot.ton_usdt is not None:
        usdt_str = f"1 TON = {format_usdt(snapshot.ton_usdt)} USDT"
    else:
        usdt_str = "1 TON = USDT: Unavailable"

    # INR row
    if snapshot.ton_inr is not None:
        inr_freshness = snapshot.get_ton_inr_freshness(stale_after_seconds)
        inr_note = " _(delayed FX)_" if inr_freshness == Freshness.DELAYED else ""
        inr_str = f"1 TON = {format_inr(snapshot.ton_inr)} INR{inr_note}"
    else:
        inr_str = "1 TON = INR: Unavailable"

    # GRAM row
    if snapshot.ton_gram is not None:
        gram_str = f"1 TON = {format_gram(snapshot.ton_gram)}"
    else:
        gram_str = "1 TON = GRAM: Unavailable"

    # Stars row
    if snapshot.ton_stars is not None:
        stars_str = f"1 TON = {format_stars(snapshot.ton_stars)}"
    else:
        stars_str = "1 TON = Telegram Stars: Rate unavailable"

    # Freshness badge
    overall_freshness = snapshot.get_overall_freshness(stale_after_seconds)
    badge = overall_freshness.badge

    # Updated timestamp
    ts_utc = format_timestamp_utc(snapshot.latest_timestamp)

    lines = [
        "💎 *TON Price*",
        "",
        usdt_str,
        inr_str,
        gram_str,
        stars_str,
        "",
        f"Last updated: {ts_utc}",
        badge,
        "",
        f"📊 Source: {snapshot.source}",
    ]
    return "\n".join(lines)


def format_live_price_message(
    snapshot: PriceSnapshot,
    stale_after_seconds: int = 15,
) -> str:
    """Format the compact live price screen message."""
    # USDT row
    usdt_val = format_usdt(snapshot.ton_usdt) if snapshot.ton_usdt is not None else "Unavailable"
    inr_val = format_inr(snapshot.ton_inr) if snapshot.ton_inr is not None else "Unavailable"
    gram_val = f"{snapshot.ton_gram:,.2f}" if snapshot.ton_gram is not None else "Unavailable"
    stars_val = f"{snapshot.ton_stars:.2f}" if snapshot.ton_stars is not None else "Rate unavailable"

    overall_freshness = snapshot.get_overall_freshness(stale_after_seconds)
    badge = overall_freshness.short_label
    ts_str = format_timestamp_utc(snapshot.latest_timestamp)

    lines = [
        "💎 *TON Live Price*",
        "",
        f"USDT: {usdt_val}",
        f"INR: {inr_val}",
        f"GRAM: {gram_val}",
        f"Stars: {stars_val}",
        "",
        badge,
        f"Updated: {ts_str}",
    ]
    return "\n".join(lines)


def format_conversion_message(
    amount: float,
    from_asset: str,
    conversions: dict[str, Optional[float]],
) -> str:
    """Format currency conversion results in clean markdown."""
    from_upper = from_asset.upper().strip()

    # Asset headers
    headers = {
        "TON": f"💎 *{amount:g} TON*",
        "USDT": f"💵 *${amount:g} USDT*",
        "INR": f"🇮🇳 *₹{amount:g} INR*",
        "GRAM": f"🪙 *{amount:g} GRAM*",
        "STARS": f"⭐ *{amount:g} Telegram Stars*",
    }
    header = headers.get(from_upper, f"💱 *{amount:g} {from_upper}*")

    lines = [
        header,
        "",
    ]

    # Target rows (exclude the from_asset itself)
    if from_upper != "TON":
        ton_val = conversions.get("TON")
        lines.append(f"≈ {format_ton(ton_val)}" if ton_val is not None else "≈ TON: Unavailable")

    if from_upper != "USDT":
        usdt_val = conversions.get("USDT")
        lines.append(f"≈ {format_usdt(usdt_val)} USDT" if usdt_val is not None else "≈ USDT: Unavailable")

    if from_upper != "INR":
        inr_val = conversions.get("INR")
        lines.append(f"≈ {format_inr(inr_val)} INR" if inr_val is not None else "≈ INR: Unavailable")

    if from_upper != "GRAM":
        gram_val = conversions.get("GRAM")
        lines.append(f"≈ {format_gram(gram_val)}" if gram_val is not None else "≈ GRAM: Unavailable")

    if from_upper not in ("STARS", "STAR"):
        stars_val = conversions.get("STARS")
        lines.append(f"≈ {format_stars(stars_val)}" if stars_val is not None else "≈ Stars: Rate unavailable")

    return "\n".join(lines)


def get_convert_menu_message() -> str:
    """Return the menu text for currency conversion."""
    return (
        "💱 *Currency Conversion*\n\n"
        "Select the currency you want to convert from, or type an amount directly in chat "
        "(e.g. `10 TON`, `100 INR`, `$20 USDT`, `1000 GRAM`, or `50 STARS`):"
    )


def get_convert_prompt_message(asset: str) -> str:
    """Return prompt message when a specific currency is chosen."""
    asset_upper = asset.upper()
    icons = {
        "TON": "💎",
        "USDT": "💵",
        "INR": "🇮🇳",
        "GRAM": "🪙",
        "STARS": "⭐",
    }
    icon = icons.get(asset_upper, "💱")
    return (
        f"{icon} *Convert from {asset_upper}*\n\n"
        f"Choose a quick amount below, or reply with any amount (e.g. `10 {asset_upper}` or `25.5`):"
    )


def get_help_message() -> str:
    """Return the /help information message."""
    return (
        "📖 *TON Price Live — User Guide*\n\n"
        "Here is everything you can do with this bot:\n\n"
        "💎 *Check Current Price:*\n"
        "• Tap *💎 TON Price* or send /price to view the current rates.\n\n"
        "🔄 *Live Refresh:*\n"
        "• Tap *🔄 Refresh* or send /refresh to fetch fresh market data immediately.\n\n"
        "💱 *Currency Conversion:*\n"
        "• Tap *💱 Convert* to pick a currency and convert quick amounts.\n"
        "• Or simply send any amount directly in the chat, for example:\n"
        "   `1 TON`\n"
        "   `10 TON`\n"
        "   `100 INR`\n"
        "   `50 USDT`\n"
        "   `1000 GRAM`\n"
        "   `500 STARS`\n\n"
        "📊 *Supported Assets:*\n"
        "• *TON* — The Open Network native token\n"
        "• *USDT* — Tether USD stablecoin\n"
        "• *INR* — Indian Rupee (calculated via live FX rates)\n"
        "• *GRAM* — On-chain GRAM jetton via TonAPI & DEX\n"
        "• *Telegram Stars* — Telegram official monetization value\n\n"
        "⚠️ *Market Disclaimer:*\n"
        "Prices are aggregated from external live market feeds (TonAPI, STON.fi, forex APIs) "
        "and fluctuate rapidly. This bot is strictly for informational purposes and does not "
        "provide financial advice."
    )


def get_about_message() -> str:
    """Return the /about information message."""
    return (
        "ℹ️ *About TON Price Live*\n\n"
        "A fast, reliable Telegram bot providing verified, current market data "
        "and instant conversions for The Open Network (TON).\n\n"
        "🏗 *Data Architecture:*\n"
        "• *Crypto Feed:* Real-time indexed rates from TonAPI with resilient REST fallback to CoinGecko and Binance.\n"
        "• *Forex Conversion:* Live USD/INR rates from official forex APIs (ExchangeRate-API, Frankfurter).\n"
        "• *GRAM Token:* Live on-chain DEX pool pricing from TonAPI and STON.fi for the official GRAM jetton.\n"
        "• *Telegram Stars:* Grounded in official Telegram terms ($0.013 USD developer monetization rate).\n\n"
        "🛡 *Integrity Guarantee:*\n"
        "• Zero hardcoded cryptocurrency prices.\n"
        "• Zero fabricated rates.\n"
        "• Transparent reporting of timestamps and sources."
    )
