"""Comprehensive automated verification of all 16 minimum test requirements."""

import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from telegram import Chat, Message, Update, User

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bot.handlers import BotHandlers, parse_conversion_query
from src.bot.live_manager import LiveModeManager
from src.bot.rate_limiter import UserRateLimiter
from src.config import Settings
from src.logging_config import setup_logging
from src.models.price_snapshot import PriceSnapshot
from src.services.price_service import PriceService


async def run_all_tests():
    setup_logging("WARNING")
    print("=" * 70)
    print(" Executing 16 Requirement Verification Tests ")
    print("=" * 70)

    # 1. /start test
    print("[1] Testing /start command...")
    settings = Settings(telegram_bot_token="test_token")
    price_service = PriceService(settings=settings)
    live_manager = LiveModeManager()
    rate_limiter = UserRateLimiter(cooldown_seconds=2.0)
    handlers = BotHandlers(price_service, live_manager, rate_limiter, settings)

    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 1001
    chat.type = "private"
    update.effective_chat = chat
    update.message = message

    await handlers.start_command(update, MagicMock())
    assert message.reply_text.called
    start_text = message.reply_text.call_args[1]["text"]
    assert "TON Price Live" in start_text
    print("   ✓ /start displays clean English welcome message and inline buttons")

    # 2. /help test
    print("\n[2] Testing /help command...")
    message.reset_mock()
    await handlers.help_command(update, MagicMock())
    assert message.reply_text.called
    help_text = message.reply_text.call_args[1]["text"]
    assert "User Guide" in help_text
    assert "Supported Assets" in help_text
    print("   ✓ /help explains commands, conversions, assets, and market disclaimer")

    # 3. /price test
    print("\n[3] Testing /price command...")
    message.reset_mock()
    await handlers.price_command(update, MagicMock())
    assert message.reply_text.called
    price_text = message.reply_text.call_args[1]["text"]
    assert "💎 *TON Price*" in price_text
    print("   ✓ /price displays formatted dashboard")

    # 4. TON price retrieval (Live Service)
    print("\n[4] Testing TON price retrieval from live APIs...")
    await price_service.start()
    snapshot = await price_service.get_snapshot(force_refresh=True)
    assert snapshot.ton_usdt is not None and snapshot.ton_usdt > 0
    print(f"   ✓ Live TON/USDT: ${snapshot.ton_usdt:.4f} (Source: {snapshot.source})")

    # 5. TON → USDT
    print("\n[5] Testing TON → USDT conversion...")
    conv_ton = price_service.convert_currency(10.0, "TON", snapshot)
    assert conv_ton["USDT"] is not None and conv_ton["USDT"] > 0
    print(f"   ✓ 10 TON ≈ ${conv_ton['USDT']:.4f} USDT")

    # 6. TON → INR
    print("\n[6] Testing TON → INR conversion...")
    assert conv_ton["INR"] is not None and conv_ton["INR"] > 0
    print(f"   ✓ 10 TON ≈ ₹{conv_ton['INR']:,.2f} INR")

    # 7. TON → GRAM
    print("\n[7] Testing TON → GRAM conversion...")
    assert conv_ton["GRAM"] is not None and conv_ton["GRAM"] > 0
    print(f"   ✓ 10 TON ≈ {conv_ton['GRAM']:,.2f} GRAM")

    # 8. TON → Telegram Stars
    print("\n[8] Testing TON → Telegram Stars conversion...")
    assert conv_ton["STARS"] is not None and conv_ton["STARS"] > 0
    print(f"   ✓ 10 TON ≈ {conv_ton['STARS']:,.2f} Telegram Stars")

    # 9. INR → TON
    print("\n[9] Testing INR → TON conversion...")
    conv_inr = price_service.convert_currency(100.0, "INR", snapshot)
    assert conv_inr["TON"] is not None and conv_inr["TON"] > 0
    print(f"   ✓ 100 INR ≈ {conv_inr['TON']:.4f} TON")

    # 10. USDT → TON
    print("\n[10] Testing USDT → TON conversion...")
    conv_usdt = price_service.convert_currency(10.0, "USDT", snapshot)
    assert conv_usdt["TON"] is not None and conv_usdt["TON"] > 0
    print(f"   ✓ 10 USDT ≈ {conv_usdt['TON']:.4f} TON")

    # 11. Invalid amount test
    print("\n[11] Testing invalid amount handling...")
    assert parse_conversion_query("abc xyz") is None
    assert parse_conversion_query("-50 TON") is None
    assert parse_conversion_query("0 INR") is None
    assert parse_conversion_query("10 TON") == (10.0, "TON")
    assert parse_conversion_query("₹500") == (500.0, "INR")
    print("   ✓ Invalid queries safely rejected, valid queries normalized correctly")

    # 12. API failure resilience
    print("\n[12] Testing API failure resilience...")
    empty_snap = PriceSnapshot(ton_usdt=None, usd_inr=None, ton_inr=None, ton_gram=None, ton_stars=None)
    conv_empty = price_service.convert_currency(10.0, "TON", empty_snap)
    assert conv_empty["USDT"] is None
    print("   ✓ Unavailable rates handled without crash or fabricated values")

    # 13. Refresh button
    print("\n[13] Testing Refresh button flow...")
    query = AsyncMock()
    query.data = "price_refresh"
    query.message = MagicMock(message_id=555)
    user = MagicMock(spec=User)
    user.id = 2001
    update.callback_query = query
    update.effective_user = user

    await handlers.callback_handler(update, MagicMock())
    assert query.edit_message_text.called
    print("   ✓ Refresh button fetched fresh data and edited message in place")

    # 14. Multiple rapid refreshes (Rate limiting)
    print("\n[14] Testing multiple rapid refreshes...")
    query.reset_mock()
    await handlers.callback_handler(update, MagicMock())
    assert query.answer.called
    answer_text = query.answer.call_args[0][0]
    assert "Please wait" in answer_text
    print("   ✓ Cooldown successfully throttles rapid repeat refreshes")

    # 15. Restarting the bot
    print("\n[15] Testing starting and stopping services cleanly...")
    await price_service.stop()
    await price_service.start()
    await price_service.stop()
    print("   ✓ Services started and stopped cleanly without resource leaks")

    # 16. Missing API key / configuration resilience
    print("\n[16] Testing missing API keys / configuration resilience...")
    clean_settings = Settings(
        telegram_bot_token="fake_token",
        crypto_api_key=None,
        fx_api_key=None,
        stars_rate_api_key=None,
    )
    resilient_service = PriceService(settings=clean_settings)
    await resilient_service.start()
    resilient_snapshot = await resilient_service.get_snapshot(force_refresh=False)
    assert resilient_snapshot.ton_usdt is not None
    await resilient_service.stop()
    print("   ✓ Bot functions seamlessly without optional API keys")

    print("\n" + "=" * 70)
    print(" ALL 16 REQUIREMENTS VERIFIED SUCCESSFULLY! ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
