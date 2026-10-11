"""Main application entrypoint initializing aiogram 3.x Bot and Dispatcher."""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.bot.handlers.commands import router as commands_router
from src.bot.handlers.links import router as links_router
from src.bot.handlers.search import router as search_router
from src.bot.middlewares.error_handler import ErrorHandlingMiddleware
from src.core.config import get_settings
from src.core.logging import get_logger, setup_logging

logger = get_logger("main")


def create_dispatcher() -> Dispatcher:
    """Configures and returns the main Dispatcher with middlewares and routers."""
    dp = Dispatcher()

    # Register global middleware
    dp.message.middleware(ErrorHandlingMiddleware())

    # Register routers
    dp.include_router(commands_router)
    dp.include_router(links_router)
    dp.include_router(search_router)

    return dp


async def main() -> None:
    """Initializes and runs the bot."""
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        pass

    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.telegram_bot_token:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set! Please supply it in your environment or .env file."
        )
        sys.exit(1)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()

    logger.info("Starting Telegram Music Downloader polling loop...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution terminated.")
