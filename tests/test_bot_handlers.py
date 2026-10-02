"""Unit tests for Telegram bot command, callback, and text conversion handlers."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Chat, Message, Update, User

from src.bot.handlers import BotHandlers, parse_conversion_query
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

    # Configure convert_currency return
    def mock_convert(amount, from_asset, snapshot):
        return {
            "TON": 10.0 if from_asset != "TON" else amount,
            "USDT": 21.845,
            "INR": 1933.30,
            "GRAM": 20000.0,
            "STARS": 1680.0,
        }

    price_service.convert_currency.side_effect = mock_convert

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
    assert parse_conversion_query("1.5 ton") == (1.5, "TON")
    assert parse_conversion_query("100 INR") == (100.0, "INR")
    assert parse_conversion_query("₹500") == (500.0, "INR")
    assert parse_conversion_query("$50") == (50.0, "USDT")
    assert parse_conversion_query("50 USDT") == (50.0, "USDT")
    assert parse_conversion_query("1000 GRAM") == (1000.0, "GRAM")
    assert parse_conversion_query("100 STARS") == (100.0, "STARS")
    assert parse_conversion_query("50 ⭐") == (50.0, "STARS")
    assert parse_conversion_query("10") == (10.0, "TON")
    assert parse_conversion_query("ton 25") == (25.0, "TON")
    assert parse_conversion_query("inr 1000") == (1000.0, "INR")
    assert parse_conversion_query("invalid query text") is None
    assert parse_conversion_query("-5 TON") is None
    assert parse_conversion_query("") is None


@pytest.mark.asyncio
async def test_start_command(mock_handlers):
    """Verify /start displays welcome message and main menu."""
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
    assert "TON Price Live" in call_kwargs["text"]
    assert "Choose an option below" in call_kwargs["text"]
    assert call_kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_price_command(mock_handlers):
    """Verify /price displays formatted prices."""
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
    assert "168.00 Stars" in text


@pytest.mark.asyncio
async def test_refresh_command_with_rate_limiting(mock_handlers):
    """Verify /refresh executes, but blocks rapid second call."""
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
    text1 = message.reply_text.call_args_list[0][1]["text"]
    assert "💎 *TON Price*" in text1

    # Call 2 (blocked by cooldown)
    await mock_handlers.refresh_command(update, context)
    assert message.reply_text.call_count == 2
    text2 = message.reply_text.call_args_list[1][0][0]
    assert "Please wait a moment before refreshing again" in text2


@pytest.mark.asyncio
async def test_convert_command(mock_handlers):
    """Verify /convert displays conversion menu."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await mock_handlers.convert_command(update, context)

    assert message.reply_text.called
    text = message.reply_text.call_args[1]["text"]
    assert "Currency Conversion" in text
    assert message.reply_text.call_args[1]["reply_markup"] is not None


@pytest.mark.asyncio
async def test_help_and_about_commands(mock_handlers):
    """Verify /help and /about output informative content."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    await mock_handlers.help_command(update, context)
    assert "User Guide" in message.reply_text.call_args[1]["text"]

    await mock_handlers.about_command(update, context)
    assert "About TON Price Live" in message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_text_message_handler_conversions(mock_handlers):
    """Verify text messages like '10 TON' or '100 INR' trigger conversions."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    update.effective_chat = chat
    update.message = message

    context = MagicMock()

    # Test '10 TON'
    message.text = "10 TON"
    await mock_handlers.text_message_handler(update, context)
    assert message.reply_text.called
    text = message.reply_text.call_args[1]["text"]
    assert "💎 *10 TON*" in text
    assert "≈ $21.8450 USDT" in text


@pytest.mark.asyncio
async def test_text_message_handler_invalid_query(mock_handlers):
    """Verify invalid text in private chat gives guidance tip."""
    update = MagicMock(spec=Update)
    message = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    update.effective_chat = chat
    update.message = message
    message.text = "hello how are you"

    context = MagicMock()

    await mock_handlers.text_message_handler(update, context)
    assert message.reply_text.called
    text = message.reply_text.call_args[0][0]
    assert "Tip" in text


@pytest.mark.asyncio
async def test_callback_price_live_and_stop(mock_handlers):
    """Verify 'price_live' and 'stop_live' callbacks."""
    update = MagicMock(spec=Update)
    query = AsyncMock()
    query.data = "price_live"
    query.message = MagicMock(message_id=888)

    chat = MagicMock(spec=Chat)
    chat.id = 12345
    user = MagicMock(spec=User)
    user.id = 999
    update.callback_query = query
    update.effective_chat = chat
    update.effective_user = user

    context = MagicMock()

    # Trigger Live Mode
    await mock_handlers.callback_handler(update, context)
    assert mock_handlers.live_manager.start_live_session.called
    assert query.edit_message_text.called
    assert "💎 *TON Live Price*" in query.edit_message_text.call_args[1]["text"]

    # Trigger Stop Live
    query.data = "stop_live"
    await mock_handlers.callback_handler(update, context)
    assert mock_handlers.live_manager.stop_live_session.called
    assert "💎 *TON Price*" in query.edit_message_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_callback_conversion_flows(mock_handlers):
    """Verify nav_convert, conv_asset_*, and conv_val_* callbacks."""
    update = MagicMock(spec=Update)
    query = AsyncMock()
    query.message = MagicMock(message_id=888)

    chat = MagicMock(spec=Chat)
    chat.id = 12345
    user = MagicMock(spec=User)
    user.id = 999
    update.callback_query = query
    update.effective_chat = chat
    update.effective_user = user

    context = MagicMock()

    # 1. Tap Convert Menu
    query.data = "nav_convert"
    await mock_handlers.callback_handler(update, context)
    assert "Currency Conversion" in query.edit_message_text.call_args[1]["text"]

    # 2. Pick Asset
    query.data = "conv_asset_ton"
    await mock_handlers.callback_handler(update, context)
    assert "Convert from TON" in query.edit_message_text.call_args[1]["text"]

    # 3. Pick quick amount
    query.data = "conv_val_ton_10"
    await mock_handlers.callback_handler(update, context)
    assert "💎 *10 TON*" in query.edit_message_text.call_args[1]["text"]


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
