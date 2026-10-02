"""Telegram bot handlers for commands, callbacks, and error reporting."""

import logging
import math
import re
from typing import Optional
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from src.bot.keyboards import get_start_keyboard
from src.bot.live_manager import LiveModeManager
from src.bot.messages import (
    format_conversion_message,
    format_current_price_message,
    format_live_price_message,
    format_multi_conversion_response,
    format_ton_conversion_response,
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


def parse_amount_token(val_str: str) -> Optional[float]:
    """Parse numeric string with optional k/m/b multiplier suffix (e.g. 1k -> 1000)."""
    s = val_str.strip().lower().replace(",", ".")
    multiplier = 1.0
    if s.endswith("k"):
        multiplier = 1_000.0
        s = s[:-1]
    elif s.endswith("m"):
        multiplier = 1_000_000.0
        s = s[:-1]
    elif s.endswith("b"):
        multiplier = 1_000_000_000.0
        s = s[:-1]
    try:
        val = float(s) * multiplier
        if val <= 0 or val > 1e12 or math.isnan(val) or math.isinf(val):
            return None
        return val
    except (ValueError, OverflowError):
        return None


def normalize_currency_symbol(curr_str: Optional[str]) -> Optional[str]:
    """Normalize currency string to standard symbol."""
    if not curr_str:
        return "TON"
    c = curr_str.upper().strip()
    if c in ("TON", "TONCOIN"):
        return "TON"
    if c in ("USDT", "USD"):
        return "USDT"
    if c in ("INR", "RS", "RUPEE", "RUPEES"):
        return "INR"
    if c in ("GRAM", "GRM"):
        return "GRAM"
    if c in ("STARS", "STAR", "⭐"):
        return "STARS"
    return None


def parse_conversion_query(text: str) -> Optional[tuple[float, str]]:
    """Parse a user text query into (amount, asset_symbol).

    Examples:
        '10 TON' -> (10.0, 'TON')
        '100 ton' -> (100.0, 'TON')
        '500 INR' -> (500.0, 'INR')
        '₹500' -> (500.0, 'INR')
        '$50' -> (50.0, 'USDT')
        '50 USDT' -> (50.0, 'USDT')
        '1000 GRAM' -> (1000.0, 'GRAM')
        '100 STARS' -> (100.0, 'STARS')
        '1k stars' -> (1000.0, 'STARS')
        '50 ⭐' -> (50.0, 'STARS')
        '10' -> (10.0, 'TON')
    """
    clean = text.strip()
    if not clean:
        return None

    # Handle ₹ prefix
    if clean.startswith("₹"):
        val = parse_amount_token(clean[1:])
        return (val, "INR") if val is not None else None

    # Handle $ prefix
    if clean.startswith("$"):
        val = parse_amount_token(clean[1:])
        return (val, "USDT") if val is not None else None

    # Pattern 1: '<amount_with_suffix> [currency]' (e.g. '100 ton', '1k stars', '500 inr', '10')
    pattern1 = r"^\s*([0-9]+(?:[\.,][0-9]+)?[kKmMbB]?)\s*([a-zA-Z⭐]+)?\s*$"
    match1 = re.match(pattern1, clean)
    if match1:
        amt_str, curr_str = match1.groups()
        amt = parse_amount_token(amt_str)
        curr = normalize_currency_symbol(curr_str)
        if amt is not None and curr is not None:
            return amt, curr

    # Pattern 2: '[currency] <amount_with_suffix>' (e.g. 'ton 100', 'stars 1k', 'inr 500')
    pattern2 = r"^\s*([a-zA-Z⭐]+)\s*([0-9]+(?:[\.,][0-9]+)?[kKmMbB]?)\s*$"
    match2 = re.match(pattern2, clean)
    if match2:
        curr_str, amt_str = match2.groups()
        amt = parse_amount_token(amt_str)
        curr = normalize_currency_symbol(curr_str)
        if amt is not None and curr is not None:
            return amt, curr

    return None


def parse_ton_input(text: str) -> Optional[float]:
    """Parse user text input to extract a valid, positive TON amount."""
    res = parse_conversion_query(text)
    if res and res[1] == "TON":
        return res[0]
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
        """Handle /start command: Show welcome message with currency selection buttons."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        text = get_welcome_message()
        keyboard = get_start_keyboard()

        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
        )

    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /price command: Fetch and show latest TON price without buttons."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        try:
            snapshot = await self.price_service.get_snapshot(force_refresh=False)
            text = format_current_price_message(
                snapshot, self.settings.price_stale_after_seconds
            )

            await update.message.reply_text(
                text=text,
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

            await update.message.reply_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error("Error in refresh_command: %s", e)
            await update.message.reply_text(
                "⚠️ Unable to retrieve the latest price right now.\n\nPlease try again shortly."
            )

    async def convert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /convert command: Prompt user to enter amount or pick currency."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        text = get_welcome_message()
        keyboard = get_start_keyboard()

        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command: Explain bot features without buttons."""
        if not update.message:
            return
        text = get_help_message()
        await update.message.reply_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /about command: Show bot and data source info without buttons."""
        if not update.effective_chat or not update.message:
            return

        chat_id = update.effective_chat.id
        await self.live_manager.stop_live_session(chat_id)

        text = get_about_message()

        await update.message.reply_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def text_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle freeform text inputs for currency conversions (e.g. '10', '100 ton', '500 inr', '1k stars')."""
        if not update.effective_chat or not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        if not text:
            return

        query_res = parse_conversion_query(text)

        if query_res is None:
            await update.message.reply_text(
                "Please enter a valid positive amount and currency.\n"
                "Examples:\n"
                "• 10 TON\n"
                "• 500 INR\n"
                "• 1k stars\n"
                "• 50 USDT"
            )
            return

        amount, from_asset = query_res

        try:
            snapshot = await self.price_service.get_snapshot(force_refresh=False)
            if snapshot.ton_usdt is None:
                await update.message.reply_text(
                    "⚠️ Live price data is temporarily unavailable. Please try again shortly."
                )
                return

            conversions = self.price_service.convert_currency(amount, from_asset, snapshot)
            reply_text = format_multi_conversion_response(amount, from_asset, conversions)

            await update.message.reply_text(
                text=reply_text,
            )
        except Exception as e:
            logger.error("Error in text_message_handler conversion: %s", e)
            await update.message.reply_text(
                "⚠️ Live price data is temporarily unavailable. Please try again shortly."
            )

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline callback query buttons."""
        query = update.callback_query
        if not query or not query.message or not update.effective_chat:
            return

        data = query.data or ""

        if data.startswith("conv_asset_"):
            asset = data.replace("conv_asset_", "").upper()
            if asset in ("STARS", "STAR"):
                asset_label = "⭐ Stars"
                example = "100 Stars or 1k stars"
            elif asset == "USDT":
                asset_label = "💵 USDT"
                example = "50 USDT or $50"
            elif asset == "INR":
                asset_label = "🇮🇳 INR"
                example = "500 INR or ₹500"
            elif asset == "GRAM":
                asset_label = "🪙 GRAM"
                example = "1000 GRAM"
            else:
                asset_label = "💎 TON"
                example = "10 TON or 10"

            msg = (
                f"Selected: {asset_label}\n\n"
                f"Now send the amount you want to convert.\n"
                f"Example: `{example}`"
            )
            await query.answer()
            await query.message.reply_text(text=msg, parse_mode=ParseMode.MARKDOWN)
            return

        await query.answer()

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
