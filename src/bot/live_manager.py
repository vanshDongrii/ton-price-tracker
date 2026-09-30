"""Multi-user live price update task manager."""

import asyncio
import logging
from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError

from src.bot.keyboards import get_live_keyboard
from src.bot.messages import format_live_price_message
from src.models.price_snapshot import PriceSnapshot
from src.services.price_service import PriceService

logger = logging.getLogger(__name__)


class LiveModeManager:
    """Manages independent, concurrent background live price streaming tasks per Telegram chat."""

    def __init__(self):
        # Maps chat_id -> background asyncio.Task
        self._active_tasks: dict[int, asyncio.Task] = {}
        # Maps chat_id -> last rendered message text (to prevent duplicate edits)
        self._last_rendered_text: dict[int, str] = {}
        self._lock = asyncio.Lock()

    def is_active(self, chat_id: int) -> bool:
        """Check if Live Mode is currently running for a specific chat."""
        task = self._active_tasks.get(chat_id)
        return task is not None and not task.done()

    @property
    def active_user_count(self) -> int:
        """Return the count of currently active Live Mode sessions."""
        return len([t for t in self._active_tasks.values() if not t.done()])

    async def start_live_session(
        self,
        chat_id: int,
        message_id: int,
        bot: Bot,
        price_service: PriceService,
        interval_seconds: int = 5,
        stale_after_seconds: int = 15,
        initial_snapshot: Optional[PriceSnapshot] = None,
    ) -> None:
        """Start or replace a live updating loop for a specific chat and message."""
        async with self._lock:
            # Cancel any existing live session for this user first
            await self._cancel_chat_task(chat_id)

            if initial_snapshot is not None:
                self._last_rendered_text[chat_id] = format_live_price_message(
                    initial_snapshot, stale_after_seconds
                )

            task_name = f"live-price-{chat_id}"
            task = asyncio.create_task(
                self._live_update_worker(
                    chat_id=chat_id,
                    message_id=message_id,
                    bot=bot,
                    price_service=price_service,
                    interval_seconds=interval_seconds,
                    stale_after_seconds=stale_after_seconds,
                ),
                name=task_name,
            )
            self._active_tasks[chat_id] = task
            logger.info("Live Mode started for chat_id=%d (interval=%ds)", chat_id, interval_seconds)

    async def stop_live_session(self, chat_id: int) -> bool:
        """Stop and cancel Live Mode for a specific chat without affecting other users."""
        async with self._lock:
            return await self._cancel_chat_task(chat_id)

    async def _cancel_chat_task(self, chat_id: int) -> bool:
        """Internal helper to cancel and clean up a chat's task."""
        task = self._active_tasks.pop(chat_id, None)
        self._last_rendered_text.pop(chat_id, None)

        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("Live Mode task cancelled for chat_id=%d", chat_id)
            return True
        return False

    async def stop_all(self) -> None:
        """Cancel all running live update tasks on application shutdown."""
        async with self._lock:
            logger.info("Stopping all active Live Mode sessions (%d active)...", len(self._active_tasks))
            for chat_id, task in list(self._active_tasks.items()):
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to cancel
            tasks = [t for t in self._active_tasks.values() if not t.done()]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self._active_tasks.clear()
            self._last_rendered_text.clear()
            logger.info("All Live Mode tasks terminated")

    async def _live_update_worker(
        self,
        chat_id: int,
        message_id: int,
        bot: Bot,
        price_service: PriceService,
        interval_seconds: int,
        stale_after_seconds: int,
    ) -> None:
        """Worker loop that throttles edits and updates the Telegram message."""
        keyboard = get_live_keyboard()

        try:
            while True:
                await asyncio.sleep(interval_seconds)

                # Retrieve latest snapshot from shared price service
                snapshot = await price_service.get_snapshot(force_refresh=False)
                new_text = format_live_price_message(snapshot, stale_after_seconds)

                # Only edit if the rendered text has changed to save Telegram API quotas
                last_text = self._last_rendered_text.get(chat_id)
                if new_text == last_text:
                    logger.debug("Live mode tick: Content unchanged for chat_id=%d, skipping edit", chat_id)
                    continue

                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=new_text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    self._last_rendered_text[chat_id] = new_text
                    logger.debug("Edited live price message for chat_id=%d", chat_id)
                except BadRequest as e:
                    # Ignore 'Message is not modified'
                    if "Message is not modified" in str(e):
                        continue
                    if "Message to edit not found" in str(e):
                        logger.warning("Live message deleted by user chat_id=%d. Ending session.", chat_id)
                        break
                    logger.warning("Telegram BadRequest during live edit for chat_id=%d: %s", chat_id, e)
                except Forbidden as e:
                    logger.warning("User blocked the bot (chat_id=%d). Ending live session: %s", chat_id, e)
                    break
                except TelegramError as e:
                    logger.warning("Telegram API error during live edit for chat_id=%d: %s", chat_id, e)

        except asyncio.CancelledError:
            logger.debug("Worker loop cancelled for chat_id=%d", chat_id)
        finally:
            self._active_tasks.pop(chat_id, None)
            self._last_rendered_text.pop(chat_id, None)
