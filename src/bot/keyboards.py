"""Telegram inline keyboards for navigation and live controls."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting a currency below the /start welcome message."""
    keyboard = [
        [
            InlineKeyboardButton("💎 TON", callback_data="conv_asset_ton"),
            InlineKeyboardButton("💵 USDT", callback_data="conv_asset_usdt"),
            InlineKeyboardButton("🇮🇳 INR", callback_data="conv_asset_inr"),
        ],
        [
            InlineKeyboardButton("🪙 GRAM", callback_data="conv_asset_gram"),
            InlineKeyboardButton("⭐ Stars", callback_data="conv_asset_stars"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu navigation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("💎 TON Price", callback_data="price_current"),
            InlineKeyboardButton("💱 Convert", callback_data="nav_convert"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="price_refresh"),
            InlineKeyboardButton("ℹ️ Help", callback_data="nav_help"),
        ],
        [
            InlineKeyboardButton("📡 Live Price", callback_data="price_live"),
            InlineKeyboardButton("ℹ️ About", callback_data="nav_about"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_price_keyboard() -> InlineKeyboardMarkup:
    """Keyboard attached to the standard price view."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="price_refresh"),
            InlineKeyboardButton("💱 Convert", callback_data="nav_convert"),
        ],
        [
            InlineKeyboardButton("📡 Live Price", callback_data="price_live"),
            InlineKeyboardButton("ℹ️ Help", callback_data="nav_help"),
        ],
        [
            InlineKeyboardButton("🔙 Main Menu", callback_data="nav_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_convert_menu_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting asset to convert from."""
    keyboard = [
        [
            InlineKeyboardButton("💎 TON", callback_data="conv_asset_ton"),
            InlineKeyboardButton("💵 USDT", callback_data="conv_asset_usdt"),
            InlineKeyboardButton("🇮🇳 INR", callback_data="conv_asset_inr"),
        ],
        [
            InlineKeyboardButton("🪙 GRAM", callback_data="conv_asset_gram"),
            InlineKeyboardButton("⭐ Telegram Stars", callback_data="conv_asset_stars"),
        ],
        [
            InlineKeyboardButton("💎 TON Price", callback_data="price_current"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="nav_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_quick_convert_keyboard(asset: str) -> InlineKeyboardMarkup:
    """Quick amounts keyboard for a specific currency."""
    asset_upper = asset.upper()
    if asset_upper == "TON":
        row1 = [
            InlineKeyboardButton("1 TON", callback_data="conv_val_ton_1"),
            InlineKeyboardButton("5 TON", callback_data="conv_val_ton_5"),
            InlineKeyboardButton("10 TON", callback_data="conv_val_ton_10"),
        ]
        row2 = [
            InlineKeyboardButton("25 TON", callback_data="conv_val_ton_25"),
            InlineKeyboardButton("50 TON", callback_data="conv_val_ton_50"),
            InlineKeyboardButton("100 TON", callback_data="conv_val_ton_100"),
        ]
    elif asset_upper == "USDT":
        row1 = [
            InlineKeyboardButton("$1 USDT", callback_data="conv_val_usdt_1"),
            InlineKeyboardButton("$5 USDT", callback_data="conv_val_usdt_5"),
            InlineKeyboardButton("$10 USDT", callback_data="conv_val_usdt_10"),
        ]
        row2 = [
            InlineKeyboardButton("$25 USDT", callback_data="conv_val_usdt_25"),
            InlineKeyboardButton("$50 USDT", callback_data="conv_val_usdt_50"),
            InlineKeyboardButton("$100 USDT", callback_data="conv_val_usdt_100"),
        ]
    elif asset_upper == "INR":
        row1 = [
            InlineKeyboardButton("₹100 INR", callback_data="conv_val_inr_100"),
            InlineKeyboardButton("₹500 INR", callback_data="conv_val_inr_500"),
            InlineKeyboardButton("₹1,000 INR", callback_data="conv_val_inr_1000"),
        ]
        row2 = [
            InlineKeyboardButton("₹2,500 INR", callback_data="conv_val_inr_2500"),
            InlineKeyboardButton("₹5,000 INR", callback_data="conv_val_inr_5000"),
            InlineKeyboardButton("₹10,000 INR", callback_data="conv_val_inr_10000"),
        ]
    elif asset_upper == "GRAM":
        row1 = [
            InlineKeyboardButton("500 GRAM", callback_data="conv_val_gram_500"),
            InlineKeyboardButton("1,000 GRAM", callback_data="conv_val_gram_1000"),
            InlineKeyboardButton("5,000 GRAM", callback_data="conv_val_gram_5000"),
        ]
        row2 = [
            InlineKeyboardButton("10,000 GRAM", callback_data="conv_val_gram_10000"),
            InlineKeyboardButton("50,000 GRAM", callback_data="conv_val_gram_50000"),
        ]
    elif asset_upper in ("STARS", "STAR"):
        row1 = [
            InlineKeyboardButton("50 Stars", callback_data="conv_val_stars_50"),
            InlineKeyboardButton("100 Stars", callback_data="conv_val_stars_100"),
            InlineKeyboardButton("250 Stars", callback_data="conv_val_stars_250"),
        ]
        row2 = [
            InlineKeyboardButton("500 Stars", callback_data="conv_val_stars_500"),
            InlineKeyboardButton("1,000 Stars", callback_data="conv_val_stars_1000"),
        ]
    else:
        row1, row2 = [], []

    keyboard = []
    if row1:
        keyboard.append(row1)
    if row2:
        keyboard.append(row2)

    keyboard.append([
        InlineKeyboardButton("💱 Other Currencies", callback_data="nav_convert"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="nav_main"),
    ])
    return InlineKeyboardMarkup(keyboard)


def get_conversion_result_keyboard() -> InlineKeyboardMarkup:
    """Keyboard attached below a conversion calculation."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh Rates", callback_data="price_refresh"),
            InlineKeyboardButton("💱 Convert Again", callback_data="nav_convert"),
        ],
        [
            InlineKeyboardButton("💎 TON Price", callback_data="price_current"),
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
            InlineKeyboardButton("💎 TON Price", callback_data="price_current"),
            InlineKeyboardButton("💱 Convert", callback_data="nav_convert"),
        ],
        [
            InlineKeyboardButton("🔙 Main Menu", callback_data="nav_main"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown on the Help screen."""
    keyboard = [
        [
            InlineKeyboardButton("💎 TON Price", callback_data="price_current"),
            InlineKeyboardButton("💱 Convert", callback_data="nav_convert"),
        ],
        [
            InlineKeyboardButton("🔙 Main Menu", callback_data="nav_main"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
