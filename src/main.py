"""Application entry point for the TON Price Tracker Telegram Bot."""

import asyncio
import logging
import signal
import sys
from typing import Optional
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from src.bot.handlers import BotHandlers
from src.bot.live_manager import LiveModeManager
from src.bot.rate_limiter import UserRateLimiter
from src.config import Settings, get_settings
from src.logging_config import setup_logging
from src.services.price_service import PriceService

logger = logging.getLogger("ton_price_tracker")


async def post_init(application: Application) -> None:
    """Invoked after bot is initialized and before polling begins."""
    bot_user = await application.bot.get_me()
    logger.info("Bot authenticated successfully: @%s (%s)", bot_user.username, bot_user.first_name)


async def post_shutdown(
    application: Application,
    price_service: PriceService,
    live_manager: LiveModeManager,
) -> None:
    """Cleanly cancel all active live tasks and close market connections."""
    logger.info("Application shutting down. Cleaning up active background tasks...")
    await live_manager.stop_all()
    await price_service.stop()
    logger.info("Shutdown completed cleanly.")


def create_application(
    settings: Settings,
    price_service: PriceService,
    live_manager: LiveModeManager,
) -> Application:
    """Build and wire the python-telegram-bot Application."""
    rate_limiter = UserRateLimiter(
        cooldown_seconds=float(settings.user_refresh_cooldown_seconds)
    )

    handlers = BotHandlers(
        price_service=price_service,
        live_manager=live_manager,
        rate_limiter=rate_limiter,
        settings=settings,
    )

    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    # Register Command Handlers
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("price", handlers.price_command))
    app.add_handler(CommandHandler("refresh", handlers.refresh_command))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("about", handlers.about_command))

    # Register Callback Query Handler
    app.add_handler(CallbackQueryHandler(handlers.callback_handler))

    # Register Error Handler
    app.add_error_handler(handlers.error_handler)

    return app


async def run_bot() -> None:
    """Main execution flow for running the bot."""
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info("==================================================")
    logger.info(" Starting TON Price Tracker Bot ")
    logger.info(" Crypto Provider: %s", settings.crypto_api_provider)
    logger.info(" FX Provider:     %s", settings.fx_api_provider)
    logger.info(" Stars Source:    %s", settings.stars_rate_source)
    logger.info(" Live Mode:       %s (interval: %ds)", settings.live_mode_enabled, settings.live_update_interval_seconds)
    logger.info("==================================================")

    if not settings.telegram_bot_token or settings.telegram_bot_token.strip() == "your_telegram_bot_token_here":
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set or contains the default placeholder. "
            "Please create a .env file and configure your Telegram bot token from @BotFather."
        )
        sys.exit(1)

    # Initialize shared services
    live_manager = LiveModeManager()
    price_service = PriceService(settings=settings)

    # Start market data WebSocket feed & FX pre-fetch
    await price_service.start()

    application = create_application(settings, price_service, live_manager)

    try:
        # Run Telegram bot polling
        async with application:
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram polling started. Ready to serve requests.")

            # Keep running until cancelled by signal or stop event
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except NotImplementedError:
                    # Windows event loop may not support add_signal_handler
                    pass

            try:
                await stop_event.wait()
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            finally:
                logger.info("Stopping polling...")
                await application.updater.stop()
                await application.stop()
    finally:
        await post_shutdown(application, price_service, live_manager)


def main() -> None:
    """Console script entry point."""
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot process exited.")


if __name__ == "__main__":
    main()
