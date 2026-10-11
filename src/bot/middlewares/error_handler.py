"""Global error handling middleware for aiogram 3.x."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.core.logging import get_logger

logger = get_logger("middleware.error")


class ErrorHandlingMiddleware(BaseMiddleware):
    """Catches unhandled handler exceptions and responds with a user-friendly message."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            logger.exception("Unhandled error occurred processing event %s: %s", type(event).__name__, exc)

            error_text = (
                "⚠️ An unexpected error occurred while processing your request.\n"
                "Please verify your link or query and try again in a few moments."
            )

            if isinstance(event, Message):
                try:
                    await event.reply(error_text)
                except Exception as reply_exc:
                    logger.error("Failed to send error reply message: %s", reply_exc)
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        "⚠️ An error occurred. Please try again.",
                        show_alert=True,
                    )
                except Exception as cb_exc:
                    logger.error("Failed to answer callback query with error: %s", cb_exc)

            return None
