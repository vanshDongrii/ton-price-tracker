"""Telegram bot handlers for commands, callbacks, and error reporting."""

import logging
import re
from typing import Optional
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    get_about_keyboard,
    get_conversion_result_keyboard,
    get_convert_menu_keyboard,
    get_help_keyboard,
    get_live_keyboard,
    get_main_menu_keyboard,
    get_price_keyboard,
    get_quick_convert_keyboard,
)
from src.bot.live_manager import LiveModeManager
from src.bot.messages import (
    format_conversion_message,
    format_current_price_message,
    format_live_price_message,
    get_about_message,
    get_convert_menu_message,
    get_convert_prompt_message,
    get_help_message,
    get_welcome_message,
)
from src.bot.rate_limiter import UserRateLimiter
from src.config import Settings
from src.services.price_service import PriceService

logger = logging.getLogger(__name__)


def parse_conversion_query(text: str) -> Optional[tuple[float, str]]:
    """Parse a user text query into (amount, asset_symbol).

    Examples:
        '10 TON' -> (10.0, 'TON')
        '100 INR' -> (100.0, 'INR')
        '₹500' -> (500.0, 'INR')
        '$50' -> (50.0, 'USDT')
        '50 USDT' -> (50.0, 'USDT')
        '1000 GRAM' -> (1000.0, 'GRAM')
        '100 STARS' -> (100.0, 'STARS')
        '50 ⭐' -> (50.0, 'STARS')
        '10' -> (10.0, 'TON')
    """
    clean = text.strip()
    if not clean:
        return None

    # Handle ₹ prefix
    if clean.startswith("₹"):
        try:
            val = float(clean[1:].strip().replace(",", ""))
            return (val, "INR") if val > 0 else None
        except ValueError:
            pass

    # Handle $ prefix
    if clean.startswith("$"):
        try:
            val = float(clean[1:].strip().replace(",", ""))
            return (val, "USDT") if val > 0 else None
        except ValueError:
            pass

    # Regex for '<amount> [currency]'
    pattern = r"^\s*([0-9]+(?:[\.,][0-9]+)?)\s*([a-zA-Z⭐]+)?\s*$"
    match = re.match(pattern, clean)
    if match:
        amount_str, curr_str = match.groups()
        try:
            amount = float(amount_str.replace(",", "."))
            if amount <= 0:
                return None
        except ValueError:
            return None

        if not curr_str:
            return amount, "TON"

        curr = curr_str.upper()
        if curr in ("TON", "TONCOIN"):
            return amount, "TON"
        if curr in ("USDT", "USD"):
            return amount, "USDT"
        if curr in ("INR", "RS", "RUPEE", "RUPEES"):
            return amount, "INR"
        if curr in ("GRAM", "GRM"):
            return amount, "GRAM"
        if curr in ("STARS", "STAR", "⭐"):
            return amount, "STARS"

    # Regex for reversed '[currency] <amount>'
    rev_pattern = r"^\s*([a-zA-Z⭐]+)\s*([0-9]+(?:[\.,][0-9]+)?)\s*$"
    rev_match = re.match(rev_pattern, clean)
    if rev_match:
        curr_str, amount_str = rev_match.groups()
        try:
            amount = float(amount_str.replace(",", "."))
            if amount <= 0:
                return None
        except ValueError:
            return None

        curr = curr_str.upper()
        if curr in ("TON", "TONCOIN"):
            return amount, "TON"
        if curr in ("USDT", "USD"):
            return amount, "USDT"
        if curr in ("INR", "RS", "RUPEE", "RUPEES"):
            return amount, "INR"
        if curr in ("GRAM", "GRM"):
            return amount, "GRAM"
        if curr in ("STARS", "STAR", "⭐"):
            return amount, "STARS"

    return None


class BotHandlers:
    """Encapsulates all Telegram bot command and callback query handlers."""

    def __init__(
        self,
        price_service: PriceService,
        live_manager: LiveModeManager,
        rate_limiter: UserRateLimiter,
        settings: Settings,
    ):
        self.price_service = price_service
        self.live_manager = live_manager
        self.rate_limiter = rate_limiter
        self.settings = settings

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command: Show welcome message and main menu."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        text = get_welcome_message()
        keyboard = get_main_menu_keyboard()

        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /price command: Fetch and show latest TON price."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        try:
            snapshot = await self.price_service.get_snapshot(force_refresh=False)
            text = format_current_price_message(
                snapshot, self.settings.price_stale_after_seconds
            )
            keyboard = get_price_keyboard()

            await update.message.reply_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error("Error in price_command: %s", e)
            await update.message.reply_text(
                "⚠️ Unable to retrieve the latest price right now.\n\nPlease try again shortly."
            )

    async def refresh_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /refresh command: Manually trigger fresh price fetch with rate limiting."""
        if not update.effective_chat or not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        allowed, remaining = self.rate_limiter.check(user_id)
        if not allowed:
            await update.message.reply_text(
                f"⏳ Please wait a moment before refreshing again ({remaining:.1f}s)."
            )
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        try:
            snapshot = await self.price_service.get_snapshot(force_refresh=True)
            text = format_current_price_message(
                snapshot, self.settings.price_stale_after_seconds
            )
            keyboard = get_price_keyboard()

            await update.message.reply_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error("Error in refresh_command: %s", e)
            await update.message.reply_text(
                "⚠️ Unable to retrieve the latest price right now.\n\nPlease try again shortly."
            )

    async def convert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /convert command: Open conversion menu."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        text = get_convert_menu_message()
        keyboard = get_convert_menu_keyboard()

        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command: Explain bot features and commands."""
        if not update.message:
            return
        text = get_help_message()
        keyboard = get_help_keyboard()
        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /about command: Show bot and data source info."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        text = get_about_message()
        keyboard = get_about_keyboard()

        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def text_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle freeform text inputs for instant currency conversions."""
        if not update.effective_chat or not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        parsed = parse_conversion_query(text)

        if parsed is None:
            if update.effective_chat.type == "private":
                await update.message.reply_text(
                    "💡 *Tip:* To convert currencies, send an amount like `10 TON`, `100 INR`, or `$50 USDT`.\n\n"
                    "Or tap /convert to choose an asset from the menu.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

        amount, asset = parsed
        try:
            snapshot = await self.price_service.get_snapshot(force_refresh=False)
            conversions = self.price_service.convert_currency(amount, asset, snapshot)
            reply_text = format_conversion_message(amount, asset, conversions)
            keyboard = get_conversion_result_keyboard()

            await update.message.reply_text(
                text=reply_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error("Error in text_message_handler conversion: %s", e)
            await update.message.reply_text(
                "⚠️ Unable to perform conversion right now. Please try again shortly."
            )

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Route and handle all inline keyboard button presses."""
        query = update.callback_query
        if not query or not query.message or not update.effective_chat or not update.effective_user:
            return

        data = query.data
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        message_id = query.message.message_id

        logger.debug("Received callback query: %s from user=%d", data, user_id)

        if data == "price_current":
            await self.live_manager.stop_live_session(chat_id)
            await query.answer()

            snapshot = await self.price_service.get_snapshot(force_refresh=False)
            text = format_current_price_message(
                snapshot, self.settings.price_stale_after_seconds
            )
            keyboard = get_price_keyboard()

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error editing to current price: %s", e)

        elif data == "price_live":
            if not self.settings.live_mode_enabled:
                await query.answer("Live Mode is currently disabled in configuration.", show_alert=True)
                return

            await query.answer("📡 Live price mode activated!")

            snapshot = await self.price_service.get_snapshot(force_refresh=False)
            initial_text = format_live_price_message(
                snapshot, self.settings.price_stale_after_seconds
            )
            live_keyboard = get_live_keyboard()

            try:
                await query.edit_message_text(
                    text=initial_text,
                    reply_markup=live_keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error editing to live price: %s", e)

            # Start background streaming loop for this user
            await self.live_manager.start_live_session(
                chat_id=chat_id,
                message_id=message_id,
                bot=context.bot,
                price_service=self.price_service,
                interval_seconds=self.settings.live_update_interval_seconds,
                stale_after_seconds=self.settings.price_stale_after_seconds,
                initial_snapshot=snapshot,
            )

        elif data == "stop_live":
            await self.live_manager.stop_live_session(chat_id)
            await query.answer("⏹ Live updates stopped")

            snapshot = await self.price_service.get_snapshot(force_refresh=False)
            text = format_current_price_message(
                snapshot, self.settings.price_stale_after_seconds
            )
            keyboard = get_price_keyboard()

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error reverting to price view: %s", e)

        elif data == "price_refresh":
            allowed, remaining = self.rate_limiter.check(user_id)
            if not allowed:
                await query.answer(
                    f"⏳ Please wait {remaining:.1f}s before refreshing again.",
                    show_alert=False,
                )
                return

            await query.answer("🔄 Updating live prices...")

            snapshot = await self.price_service.get_snapshot(force_refresh=True)
            text = format_current_price_message(
                snapshot, self.settings.price_stale_after_seconds
            )
            keyboard = get_price_keyboard()

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error refreshing price: %s", e)

        elif data == "nav_convert":
            await self.live_manager.stop_live_session(chat_id)
            await query.answer()

            text = get_convert_menu_message()
            keyboard = get_convert_menu_keyboard()

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error navigating to convert menu: %s", e)

        elif data.startswith("conv_asset_"):
            await self.live_manager.stop_live_session(chat_id)
            await query.answer()

            asset_code = data.replace("conv_asset_", "").upper()
            text = get_convert_prompt_message(asset_code)
            keyboard = get_quick_convert_keyboard(asset_code)

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error opening quick convert for %s: %s", asset_code, e)

        elif data.startswith("conv_val_"):
            await query.answer()
            # Format: conv_val_<asset>_<amount>
            parts = data.split("_")
            if len(parts) >= 4:
                asset_code = parts[2].upper()
                try:
                    amount = float(parts[3])
                except ValueError:
                    amount = 1.0

                snapshot = await self.price_service.get_snapshot(force_refresh=False)
                conversions = self.price_service.convert_currency(amount, asset_code, snapshot)
                reply_text = format_conversion_message(amount, asset_code, conversions)
                keyboard = get_conversion_result_keyboard()

                try:
                    await query.edit_message_text(
                        text=reply_text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        logger.warning("Error displaying conversion result: %s", e)

        elif data == "nav_help":
            await self.live_manager.stop_live_session(chat_id)
            await query.answer()

            text = get_help_message()
            keyboard = get_help_keyboard()

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error navigating to help: %s", e)

        elif data == "nav_about":
            await self.live_manager.stop_live_session(chat_id)
            await query.answer()

            text = get_about_message()
            keyboard = get_about_keyboard()

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error navigating to about: %s", e)

        elif data == "nav_main":
            await self.live_manager.stop_live_session(chat_id)
            await query.answer()

            text = get_welcome_message()
            keyboard = get_main_menu_keyboard()

            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning("Error navigating to main menu: %s", e)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Global exception handler for Telegram updates."""
        logger.error("Exception while handling Telegram update: %s", context.error, exc_info=context.error)

        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ An unexpected error occurred while processing your request.\n\nPlease try again shortly."
                )
            except Exception as e:
                logger.error("Failed to send error notification message: %s", e)
