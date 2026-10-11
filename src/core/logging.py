"""Structured logging setup for the Telegram Music Downloader application."""

import logging
import sys
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """
    Configures and initializes logging for the entire application.

    Args:
        log_level: String level (e.g. 'DEBUG', 'INFO', 'WARNING'). If omitted, defaults to 'INFO'.

    Returns:
        Root logger instance.
    """
    level = getattr(logging, (log_level or "INFO").upper(), logging.INFO)

    log_format = (
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Silence overly verbose third-party loggers
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger("music_bot")
    logger.setLevel(level)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance scoped to the specified module name."""
    return logging.getLogger(f"music_bot.{name}")
