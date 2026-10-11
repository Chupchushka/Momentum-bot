"""Command handlers for /start and /help in aiogram 3.x."""

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from src.bot.ui.messages import HELP_MESSAGE, WELCOME_MESSAGE
from src.core.logging import get_logger

logger = get_logger("handlers.commands")
router = Router(name="commands")


@router.message(CommandStart())
async def handle_start_command(message: Message) -> None:
    """Handles the /start command and welcomes the user."""
    logger.info("User %s started the bot", message.from_user.id if message.from_user else "unknown")
    await message.answer(
        text=WELCOME_MESSAGE,
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def handle_help_command(message: Message) -> None:
    """Handles the /help command and displays usage guidance."""
    await message.answer(
        text=HELP_MESSAGE,
        parse_mode=ParseMode.HTML,
    )
