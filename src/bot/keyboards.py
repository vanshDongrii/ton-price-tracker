"""Telegram inline keyboards for navigation and live controls."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu navigation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("💰 Current Price", callback_data="price_current"),
            InlineKeyboardButton("📡 Live Price", callback_data="price_live"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="price_refresh"),
            InlineKeyboardButton("ℹ️ About", callback_data="nav_about"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_price_keyboard() -> InlineKeyboardMarkup:
    """Keyboard attached to the standard price view."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="price_refresh"),
            InlineKeyboardButton("📡 Live Price", callback_data="price_live"),
        ],
        [
            InlineKeyboardButton("ℹ️ About", callback_data="nav_about"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="nav_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_live_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during active Live Mode."""
    keyboard = [
        [
            InlineKeyboardButton("⏹ Stop Live Updates", callback_data="stop_live"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_about_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown on the About screen."""
    keyboard = [
        [
            InlineKeyboardButton("💰 Current Price", callback_data="price_current"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="nav_main"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
