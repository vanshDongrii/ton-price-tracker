"""Unit tests for Telegram bot command, callback, and text conversion handlers."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ParseMode

from src.bot.handlers import BotHandlers, parse_conversion_query, parse_ton_input
from src.bot.live_manager import LiveModeManager
from src.bot.rate_limiter import UserRateLimiter
from src.config import Settings
from src.models.price_snapshot import PriceSnapshot
from src.services.price_service import PriceService


@pytest.fixture
def sample_snapshot():
    now_utc = datetime.now(timezone.utc)
    return PriceSnapshot(
        ton_usdt=2.1845,
        usd_inr=88.50,
        ton_inr=193.33,
        ton_gram=2000.0,
        ton_stars=168.0,
        ton_usdt_timestamp=now_utc,
        usd_inr_timestamp=now_utc,
        ton_inr_timestamp=now_utc,
        ton_gram_timestamp=now_utc,
        stars_timestamp=now_utc,
        source="TonAPI + ExchangeRate-API",
        feed_type="REST",
    )


@pytest.fixture
def mock_handlers(sample_snapshot):
    settings = Settings(
        telegram_bot_token="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_mock",
        live_mode_enabled=True,
        live_update_interval_seconds=5,
        price_stale_after_seconds=15,
        user_refresh_cooldown_seconds=3,
    )
    price_service = AsyncMock(spec=PriceService)
    price_service.get_snapshot.return_value = sample_snapshot

    # Use real convert_currency logic on sample snapshot
    real_service = PriceService()
    price_service.convert_currency.side_effect = real_service.convert_currency

    live_manager = AsyncMock(spec=LiveModeManager)
    rate_limiter = UserRateLimiter(cooldown_seconds=3.0)

    return BotHandlers(
        price_service=price_service,
        live_manager=live_manager,
        rate_limiter=rate_limiter,
        settings=settings,
    )


def test_parse_conversion_query():
    """Verify natural-language amount and currency parsing."""
    assert parse_conversion_query("10 TON") == (10.0, "TON")
    assert parse_conversion_query("100 ton") == (100.0, "TON")
    assert parse_conversion_query("1.5 ton") == (1.5, "TON")
    assert parse_conversion_query("100 INR") == (100.0, "INR")
    assert parse_conversion_query("500 inr") == (500.0, "INR")
    assert parse_conversion_query("₹500") == (500.0, "INR")
    assert parse_conversion_query("$50") == (50.0, "USDT")
    assert parse_conversion_query("50 USDT") == (50.0, "USDT")
    assert parse_conversion_query("1t") == (1.0, "TON")
    assert parse_conversion_query("1g") == (1.0, "TON")
    assert parse_conversion_query("1 gram") == (1.0, "TON")
    assert parse_conversion_query("1u") == (1.0, "USDT")
    assert parse_conversion_query("1usdt") == (1.0, "USDT")
    assert parse_conversion_query("1$") == (1.0, "USDT")
    assert parse_conversion_query("100s") == (100.0, "STARS")
    assert parse_conversion_query("100star") == (100.0, "STARS")
    assert parse_conversion_query("100r") == (100.0, "INR")
    assert parse_conversion_query("100rs") == (100.0, "INR")
    assert parse_conversion_query("100₹") == (100.0, "INR")
    assert parse_conversion_query("1000 GRAM") == (1000.0, "TON")
    assert parse_conversion_query("100 STARS") == (100.0, "STARS")
    assert parse_conversion_query("1k stars") == (1000.0, "STARS")
    assert parse_conversion_query("2.5k stars") == (2500.0, "STARS")
    assert parse_conversion_query("50 ⭐") == (50.0, "STARS")
    assert parse_conversion_query("10") == (10.0, "TON")
    assert parse_conversion_query("ton 25") == (25.0, "TON")
    assert parse_conversion_query("inr 1000") == (1000.0, "INR")
    assert parse_conversion_query("invalid query text") is None
    assert parse_conversion_query("-5 TON") is None
    assert parse_conversion_query("") is None


def test_parse_ton_input():
    """Verify numeric TON amount parsing and strict validation."""
    assert parse_ton_input("10") == 10.0
    assert parse_ton_input("10 TON") == 10.0
    assert parse_ton_input("10 ton") == 10.0
    assert parse_ton_input("10.5") == 10.5
    assert parse_ton_input("0.25 TON") == 0.25
    assert parse_ton_input("0.25 ton") == 0.25
    assert parse_ton_input("10,5") == 10.5
    assert parse_ton_input("10,5 TON") == 10.5
    assert parse_ton_input("TON 10") == 10.0
    assert parse_ton_input("  10.5  ") == 10.5

    # Invalid inputs
    assert parse_ton_input("hello") is None
    assert parse_ton_input("TON") is None
    assert parse_ton_input("-10") is None
    assert parse_ton_input("-10 TON") is None
    assert parse_ton_input("0") is None
    assert parse_ton_input("0.0") is None
    assert parse_ton_input("0 TON") is None
    assert parse_ton_input("") is None
    assert parse_ton_input("   ") is None
    assert parse_ton_input("10 USDT") is None
    assert parse_ton_input("999999999999999999999999999999") is None


@pytest.mark.asyncio
async def test_start_command(mock_handlers):
    """Verify /start displays Pavel Kurs welcome message with currency selection keyboard."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await mock_handlers.start_command(update, context)

    assert message.reply_text.called
    call_kwargs = message.reply_text.call_args[1]
    text = call_kwargs["text"]
    assert "Pavel Kurs" in text
    assert "converter for TON, USDT, Stars, and INR" in text
    assert "select a currency using the button below" in text
    assert call_kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_price_command(mock_handlers):
    """Verify /price displays formatted prices without keyboards."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await mock_handlers.price_command(update, context)

    assert message.reply_text.called
    call_kwargs = message.reply_text.call_args[1]
    text = call_kwargs["text"]
    assert "💎 *TON Price*" in text
    assert "$2.1845" in text
    assert "₹193.33" in text
    assert "2,000.00 GRAM" in text
    assert "168 Stars" in text
    assert call_kwargs.get("reply_markup") is None


@pytest.mark.asyncio
async def test_refresh_command_with_rate_limiting(mock_handlers):
    """Verify /refresh executes without keyboard, but blocks rapid second call."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    user = MagicMock(spec=User)
    user.id = 999
    update.effective_chat = chat
    update.effective_user = user
    update.message = message

    context = MagicMock()

    # Call 1 (allowed)
    await mock_handlers.refresh_command(update, context)
    assert message.reply_text.call_count == 1
    call_kwargs = message.reply_text.call_args_list[0][1]
    text1 = call_kwargs["text"]
    assert "💎 *TON Price*" in text1
    assert call_kwargs.get("reply_markup") is None

    # Call 2 (blocked by cooldown)
    await mock_handlers.refresh_command(update, context)
    assert message.reply_text.call_count == 2
    text2 = message.reply_text.call_args_list[1][0][0]
    assert "Please wait a moment before refreshing again" in text2


@pytest.mark.asyncio
async def test_convert_command(mock_handlers):
    """Verify /convert prompts user with currency selection keyboard."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await mock_handlers.convert_command(update, context)

    assert message.reply_text.called
    call_kwargs = message.reply_text.call_args[1]
    text = call_kwargs["text"]
    assert "Pavel Kurs" in text
    assert call_kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_help_and_about_commands(mock_handlers):
    """Verify /help and /about output informative content without keyboards."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await mock_handlers.help_command(update, context)
    help_kwargs = message.reply_text.call_args[1]
    assert "User Guide" in help_kwargs["text"]
    assert help_kwargs.get("reply_markup") is None

    await mock_handlers.about_command(update, context)
    about_kwargs = message.reply_text.call_args[1]
    assert "About TON Price Live" in about_kwargs["text"]
    assert about_kwargs.get("reply_markup") is None


@pytest.mark.asyncio
async def test_text_message_handler_conversions(mock_handlers):
    """Verify numeric text inputs trigger conversion in expected clean format."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    # 1. Test '10'
    message.text = "10"
    await mock_handlers.text_message_handler(update, context)
    assert message.reply_text.called
    call_kwargs = message.reply_text.call_args[1]
    text = call_kwargs["text"]
    expected_10 = (
        "🔄 Converting 10 TON\n"
        "*TON 💎*: 10\n"
        "*USDT 💵*: 21.8450\n"
        "*STARS ⭐*: 1,680\n"
        "*INR 🇮🇳*: 1,933.30"
    )
    assert text == expected_10
    assert call_kwargs.get("parse_mode") == ParseMode.MARKDOWN
    assert call_kwargs.get("reply_markup") is None

    # 2. Test '10 TON'
    message.text = "10 TON"
    await mock_handlers.text_message_handler(update, context)
    call_kwargs = message.reply_text.call_args[1]
    assert call_kwargs["text"] == expected_10
    assert call_kwargs.get("reply_markup") is None

    # 3. Test '10.5'
    message.text = "10.5"
    await mock_handlers.text_message_handler(update, context)
    call_kwargs = message.reply_text.call_args[1]
    assert "🔄 Converting 10.5 TON" in call_kwargs["text"]
    assert call_kwargs.get("reply_markup") is None

    # 4. Test '0.25 TON'
    message.text = "0.25 TON"
    await mock_handlers.text_message_handler(update, context)
    call_kwargs = message.reply_text.call_args[1]
    assert "🔄 Converting 0.25 TON" in call_kwargs["text"]
    assert call_kwargs.get("reply_markup") is None

    # 5. Test '500 inr'
    message.text = "500 inr"
    await mock_handlers.text_message_handler(update, context)
    call_kwargs = message.reply_text.call_args[1]
    assert "🔄 Converting 500 INR" in call_kwargs["text"]
    assert "*TON 💎*:" in call_kwargs["text"]

    # 6. Test '1k stars'
    message.text = "1k stars"
    await mock_handlers.text_message_handler(update, context)
    call_kwargs = message.reply_text.call_args[1]
    assert "🔄 Converting 1,000 STARS" in call_kwargs["text"]
    assert "*TON 💎*:" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_text_message_handler_invalid_inputs(mock_handlers):
    """Verify invalid inputs safely return guidance message without crashing."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()
    expected_error = "Please enter a valid positive amount and currency."

    invalid_cases = ["hello", "-10", "0", "0.0", "-5 TON", "random text"]

    for invalid_text in invalid_cases:
        message.text = invalid_text
        await mock_handlers.text_message_handler(update, context)
        assert message.reply_text.called
        reply = message.reply_text.call_args[0][0]
        assert expected_error in reply


@pytest.mark.asyncio
async def test_text_message_handler_api_failure(mock_handlers):
    """Verify error message when price snapshot is unavailable."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message
    message.text = "10 TON"

    context = MagicMock()

    # Case 1: ton_usdt is None
    unavailable_snapshot = PriceSnapshot(
        ton_usdt=None,
        usd_inr=None,
        ton_inr=None,
        ton_gram=None,
        ton_stars=None,
        source="Unavailable",
        feed_type="None",
    )
    mock_handlers.price_service.get_snapshot.return_value = unavailable_snapshot

    await mock_handlers.text_message_handler(update, context)
    assert message.reply_text.called
    assert "temporarily unavailable" in message.reply_text.call_args[0][0]

    # Case 2: price_service throws an exception
    mock_handlers.price_service.get_snapshot.side_effect = RuntimeError("API timeout")
    await mock_handlers.text_message_handler(update, context)
    assert "temporarily unavailable" in message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_handler_currency_selection(mock_handlers):
    """Verify inline currency buttons answer and prompt user for amount."""
    update = MagicMock(spec=Update)
    query = AsyncMock()
    query.data = "conv_asset_stars"
    message = AsyncMock(spec=Message)
    query.message = message

    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.callback_query = query
    update.effective_chat = chat

    context = MagicMock()

    await mock_handlers.callback_handler(update, context)
    assert query.answer.called
    assert message.reply_text.called
    reply = message.reply_text.call_args[1]["text"]
    assert "Selected: ⭐ Stars" in reply
    assert "1k stars" in reply


@pytest.mark.asyncio
async def test_global_error_handler(mock_handlers):
    """Verify error handler notifies user safely without leaking stack trace."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    update.effective_message = message

    context = MagicMock()
    context.error = RuntimeError("Database connection timed out with secret=XYZ123")

    await mock_handlers.error_handler(update, context)

    assert message.reply_text.called
    error_msg = message.reply_text.call_args[0][0]
    assert "error occurred while processing your request" in error_msg
    assert "secret=XYZ123" not in error_msg

