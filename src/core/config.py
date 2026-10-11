"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot Token
    telegram_bot_token: str = Field(
        default="",
        alias="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token obtained from @BotFather",
    )

    # Ephemeral Storage Settings
    temp_dir: Path = Field(
        default=Path("/tmp/music_bot_tmp"),
        alias="TEMP_DIR",
        description="Path to temporary directory for audio processing",
    )

    # Audio & Platform Constraints
    max_file_size_bytes: int = Field(
        default=52_428_800,
        alias="MAX_FILE_SIZE_BYTES",
        description="Maximum audio file size allowed (Telegram limit is 50MB)",
    )
    max_duration_seconds: int = Field(
        default=1200,
        alias="MAX_DURATION_SECONDS",
        description="Maximum track duration in seconds (20 minutes)",
    )

    # Optional Spotify API Credentials
    spotify_client_id: Optional[str] = Field(
        default=None,
        alias="SPOTIFY_CLIENT_ID",
        description="Optional Spotify Developer Client ID for enhanced metadata",
    )
    spotify_client_secret: Optional[str] = Field(
        default=None,
        alias="SPOTIFY_CLIENT_SECRET",
        description="Optional Spotify Developer Client Secret for enhanced metadata",
    )
    # Cache & Concurrency Settings
    cache_db_path: Path = Field(
        default=Path("cache.db"),
        alias="CACHE_DB_PATH",
        description="Path to SQLite database used for Telegram file_id caching",
    )
    max_concurrent_downloads: int = Field(
        default=4,
        alias="MAX_CONCURRENT_DOWNLOADS",
        description="Semaphore threshold for concurrent audio extractions",
    )
    download_timeout_seconds: int = Field(
        default=60,
        alias="DOWNLOAD_TIMEOUT_SECONDS",
        description="Timeout threshold for audio download and conversion",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    def ensure_temp_dir(self) -> Path:
        """Ensure the temporary directory exists and return it."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self.temp_dir


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    settings = Settings()
    settings.ensure_temp_dir()
    return settings
