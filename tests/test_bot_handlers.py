"""Unit tests for Telegram bot command and callback handlers."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Chat, Message, Update, User

from src.bot.handlers import BotHandlers
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
        ton_stars=None,
        ton_usdt_timestamp=now_utc,
        usd_inr_timestamp=now_utc,
        ton_inr_timestamp=now_utc,
        stars_timestamp=None,
        source="Whitebit (WS) + ExchangeRate-API",
        feed_type="WebSocket",
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

    live_manager = AsyncMock(spec=LiveModeManager)
    rate_limiter = UserRateLimiter(cooldown_seconds=3.0)

    return BotHandlers(
        price_service=price_service,
        live_manager=live_manager,
        rate_limiter=rate_limiter,
        settings=settings,
    )


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
    assert "💎 *TON Price Tracker*" in call_kwargs["text"]
    assert "Choose an option below:" in call_kwargs["text"]
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
    assert "💎 *TON Current Price*" in text
    assert "$2.1845" in text
    assert "₹193.33" in text
    assert "⭐ *Stars: Rate unavailable*" in text
    assert "🟢 Live market data" in text


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
    assert "💎 *TON Current Price*" in text1

    # Call 2 (blocked by cooldown)
    await mock_handlers.refresh_command(update, context)
    assert message.reply_text.call_count == 2
    text2 = message.reply_text.call_args_list[1][0][0]
    assert "Please wait a moment before refreshing again" in text2


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
    assert "About TON Price Tracker" in message.reply_text.call_args[1]["text"]


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
    assert "💎 *TON Current Price*" in query.edit_message_text.call_args[1]["text"]


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
    assert "Unable to retrieve the latest price right now" in error_msg
    assert "secret=XYZ123" not in error_msg


@pytest.mark.asyncio
async def test_callback_refresh_with_cooldown(mock_handlers):
    """Verify refresh button respects rate limiter and answers callback queries."""
    update = MagicMock(spec=Update)
    query = AsyncMock()
    query.data = "price_refresh"
    query.message = MagicMock(message_id=888)

    chat = MagicMock(spec=Chat)
    chat.id = 12345
    user = MagicMock(spec=User)
    user.id = 777
    update.callback_query = query
    update.effective_chat = chat
    update.effective_user = user

    context = MagicMock()

    # Click 1: Allowed
    await mock_handlers.callback_handler(update, context)
    assert query.edit_message_text.called
    assert query.answer.called

    # Click 2: Rapid repeat should trigger cooldown warning
    await mock_handlers.callback_handler(update, context)
    last_answer = query.answer.call_args[0][0]
    assert "Please wait" in last_answer


@pytest.mark.asyncio
async def test_callback_navigation(mock_handlers):
    """Verify nav_about and nav_main callbacks."""
    update = MagicMock(spec=Update)
    query = AsyncMock()
    query.data = "nav_about"
    query.message = MagicMock(message_id=888)

    chat = MagicMock(spec=Chat)
    chat.id = 12345
    user = MagicMock(spec=User)
    user.id = 888
    update.callback_query = query
    update.effective_chat = chat
    update.effective_user = user

    context = MagicMock()

    # Navigate to About
    await mock_handlers.callback_handler(update, context)
    assert "About TON Price Tracker" in query.edit_message_text.call_args[1]["text"]

    # Navigate to Main Menu
    query.data = "nav_main"
    await mock_handlers.callback_handler(update, context)
    assert "Choose an option below:" in query.edit_message_text.call_args[1]["text"]

