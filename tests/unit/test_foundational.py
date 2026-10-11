"""Unit tests for foundational Phase 2 components."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from src.services.metadata.base import (
    AudioDeliverable,
    RequestType,
    TrackMetadata,
    UserRequest,
)
from src.services.cache.repository import CacheRepository, CachedTrack
from src.bot.ui.messages import msg_searching, WELCOME_MESSAGE
from src.main import create_dispatcher


def test_user_request_model():
    req = UserRequest(
        user_id=12345,
        chat_id=67890,
        message_id=1,
        raw_input="Queen - Bohemian Rhapsody",
        request_type=RequestType.TEXT_SEARCH,
    )
    assert req.user_id == 12345
    assert req.request_type == RequestType.TEXT_SEARCH
    assert req.request_id is not None


def test_track_metadata_duration_validation():
    # Valid metadata
    valid = TrackMetadata(
        track_id="yt:123",
        title="Bohemian Rhapsody",
        artist="Queen",
        duration_seconds=354,
        source_url="https://youtube.com/watch?v=123",
    )
    assert valid.duration_seconds == 354

    # Duration > 1200 seconds should fail validation
    with pytest.raises(ValidationError):
        TrackMetadata(
            track_id="yt:123",
            title="Long Podcast",
            artist="Host",
            duration_seconds=1300,
            source_url="https://youtube.com/watch?v=123",
        )


def test_audio_deliverable_format_and_size_validation(tmp_path: Path):
    audio_file = tmp_path / "song.mp3"
    audio_file.write_bytes(b"dummy audio content")

    deliverable = AudioDeliverable(
        file_path=audio_file,
        file_size_bytes=1024,
        bitrate_kbps=320,
        duration_seconds=200,
        format="mp3",
    )
    assert deliverable.format == "mp3"

    # Non-mp3 format must be rejected
    with pytest.raises(ValidationError):
        AudioDeliverable(
            file_path=audio_file,
            file_size_bytes=1024,
            bitrate_kbps=320,
            duration_seconds=200,
            format="wav",
        )

    # Exceeding 50MB must be rejected
    with pytest.raises(ValidationError):
        AudioDeliverable(
            file_path=audio_file,
            file_size_bytes=60_000_000,
            bitrate_kbps=320,
            duration_seconds=200,
            format="mp3",
        )


def test_cache_repository(tmp_path: Path):
    db_file = tmp_path / "test_cache.db"
    repo = CacheRepository(db_path=db_file)

    # Key normalization
    norm_key = repo.normalize_query_key("Queen - Bohemian Rhapsody!")
    assert norm_key == "search:bohemian_queen_rhapsody"

    # Put and get
    item = CachedTrack(
        cache_key="yt:dQw4w9WgXcQ",
        telegram_file_id="CQACAgIAAxkBAAE...",
        title="Never Gonna Give You Up",
        artist="Rick Astley",
        duration_seconds=213,
    )
    repo.put(item)

    retrieved = repo.get("yt:dQw4w9WgXcQ")
    assert retrieved is not None
    assert retrieved.telegram_file_id == "CQACAgIAAxkBAAE..."
    assert retrieved.hit_count == 1

    # Second hit
    retrieved2 = repo.get("yt:dQw4w9WgXcQ")
    assert retrieved2.hit_count == 2


def test_ui_messages():
    msg = msg_searching("Adele")
    assert "Adele" in msg
    assert "Searching" in msg
    assert len(WELCOME_MESSAGE) > 0


def test_dispatcher_creation():
    dp = create_dispatcher()
    assert dp is not None
    assert len(dp.sub_routers) >= 1
