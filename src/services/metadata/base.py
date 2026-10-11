"""Base domain models and abstractions for track metadata and user requests."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class RequestType(str, Enum):
    """Types of user requests recognized by the bot."""

    TEXT_SEARCH = "TEXT_SEARCH"
    SPOTIFY_URL = "SPOTIFY_URL"
    YOUTUBE_URL = "YOUTUBE_URL"
    UNSUPPORTED = "UNSUPPORTED"


class UserRequest(BaseModel):
    """Represents an incoming interaction from a Telegram user."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: int = Field(gt=0, description="Telegram User ID")
    chat_id: int = Field(description="Telegram Chat ID")
    message_id: int = Field(description="Telegram Message ID for replies")
    raw_input: str = Field(min_length=1, max_length=500, description="Raw query text or URL")
    request_type: RequestType = Field(default=RequestType.UNSUPPORTED)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrackMetadata(BaseModel):
    """Normalized metadata for a musical track across all supported sources."""

    track_id: str = Field(min_length=1, description="Normalized track identifier")
    title: str = Field(min_length=1, max_length=200, description="Track title")
    artist: str = Field(min_length=1, max_length=200, description="Artist name")
    album: Optional[str] = Field(default=None, max_length=200, description="Album name")
    duration_seconds: int = Field(
        ge=1,
        le=1200,
        description="Duration in seconds (enforces max 20 minutes limit)",
    )
    cover_art_url: Optional[str] = Field(default=None, description="URL of cover artwork")
    source_url: str = Field(min_length=1, description="Canonical source streaming URL")


class AudioDeliverable(BaseModel):
    """Represents a generated MP3 audio file ready for delivery."""

    file_path: Path = Field(description="Local path to generated MP3 file")
    cover_path: Optional[Path] = Field(default=None, description="Local path to cover artwork thumbnail")
    file_size_bytes: int = Field(
        gt=0,
        le=52_428_800,
        description="File size in bytes (max 50 MB Telegram upload limit)",
    )
    bitrate_kbps: int = Field(
        default=320,
        ge=64,
        le=320,
        description="Audio bitrate in kbps",
    )
    duration_seconds: int = Field(ge=1, description="Audio duration in seconds")
    format: str = Field(default="mp3", description="Audio format container")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        if value.lower() != "mp3":
            raise ValueError("AudioDeliverable format must strictly be 'mp3'")
        return "mp3"


class MetadataResolver(ABC):
    """Abstract base class for URL and search query resolvers."""

    @abstractmethod
    def can_handle(self, raw_input: str) -> bool:
        """Determines if this resolver matches the input syntax."""
        pass

    @abstractmethod
    async def resolve(self, raw_input: str) -> TrackMetadata:
        """Resolves raw input to canonical TrackMetadata."""
        pass
