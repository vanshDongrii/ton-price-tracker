"""Unit tests for LiveModeManager: multi-user isolation, cancellation, and message throttling."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.bot.live_manager import LiveModeManager
from src.models.price_snapshot import PriceSnapshot


@pytest.mark.asyncio
async def test_live_session_lifecycle():
    """Verify start, active check, and stop of live mode session."""
    manager = LiveModeManager()
    bot = AsyncMock()

    price_service = AsyncMock()
    now_utc = datetime.now(timezone.utc)
    snapshot = PriceSnapshot(
        ton_usdt=2.1845,
        usd_inr=88.50,
        ton_inr=193.33,
        ton_stars=None,
        ton_usdt_timestamp=now_utc,
        usd_inr_timestamp=now_utc,
        ton_inr_timestamp=now_utc,
        source="Test",
        feed_type="WebSocket",
    )
    price_service.get_snapshot.return_value = snapshot

    chat_id = 999
    message_id = 1234

    await manager.start_live_session(
        chat_id=chat_id,
        message_id=message_id,
        bot=bot,
        price_service=price_service,
        interval_seconds=1,
        stale_after_seconds=15,
        initial_snapshot=snapshot,
    )

    assert manager.is_active(chat_id) is True
    assert manager.active_user_count == 1

    # Stop session
    stopped = await manager.stop_live_session(chat_id)
    assert stopped is True
    assert manager.is_active(chat_id) is False
    assert manager.active_user_count == 0


@pytest.mark.asyncio
async def test_multi_user_isolation():
    """Verify that multiple users have independent tasks and stopping one does not affect others."""
    manager = LiveModeManager()
    bot = AsyncMock()
    price_service = AsyncMock()

    now_utc = datetime.now(timezone.utc)
    snapshot = PriceSnapshot(
        ton_usdt=2.1845,
        usd_inr=88.50,
        ton_inr=193.33,
        ton_usdt_timestamp=now_utc,
        usd_inr_timestamp=now_utc,
        ton_inr_timestamp=now_utc,
    )
    price_service.get_snapshot.return_value = snapshot

    # Start User A, User B, User C
    await manager.start_live_session(101, 1, bot, price_service, 10, 15)
    await manager.start_live_session(102, 2, bot, price_service, 10, 15)
    await manager.start_live_session(103, 3, bot, price_service, 10, 15)

    assert manager.active_user_count == 3
    assert manager.is_active(101) is True
    assert manager.is_active(102) is True
    assert manager.is_active(103) is True

    # Stop User A
    await manager.stop_live_session(101)

    assert manager.is_active(101) is False
    assert manager.is_active(102) is True  # User B unaffected!
    assert manager.is_active(103) is True  # User C unaffected!
    assert manager.active_user_count == 2

    # Clean shutdown
    await manager.stop_all()
    assert manager.active_user_count == 0


@pytest.mark.asyncio
async def test_live_message_throttling_skips_unchanged():
    """Live worker does not call edit_message_text if the rendered text is identical."""
    manager = LiveModeManager()
    bot = AsyncMock()
    price_service = AsyncMock()

    now_utc = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
    static_snapshot = PriceSnapshot(
        ton_usdt=2.0000,
        usd_inr=80.00,
        ton_inr=160.00,
        ton_stars=None,
        ton_usdt_timestamp=now_utc,
        usd_inr_timestamp=now_utc,
        ton_inr_timestamp=now_utc,
    )
    price_service.get_snapshot.return_value = static_snapshot

    # Start session with initial_snapshot pre-set to static_snapshot
    await manager.start_live_session(
        chat_id=555,
        message_id=777,
        bot=bot,
        price_service=price_service,
        interval_seconds=1,
        stale_after_seconds=15,
        initial_snapshot=static_snapshot,
    )

    # Let worker tick once
    await asyncio.sleep(1.2)

    # Since initial_snapshot was already recorded and content didn't change,
    # edit_message_text should not be called!
    assert bot.edit_message_text.call_count == 0

    await manager.stop_live_session(555)
