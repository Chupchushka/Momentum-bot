"""Unit tests for SearchResolver (User Story 1)."""

import pytest
from unittest.mock import AsyncMock, patch

from src.services.metadata.base import TrackMetadata
from src.services.audio.extractor import DurationLimitExceededError, TrackNotFoundError


@pytest.fixture
def mock_extractor():
    extractor = AsyncMock()
    extractor.get_metadata_info.return_value = {
        "id": "fJ9rUzIMcZQ",
        "title": "Queen - Bohemian Rhapsody (Official Video Remastered)",
        "artist": "Queen",
        "track": "Bohemian Rhapsody",
        "duration": 354,
        "thumbnail": "https://i.ytimg.com/vi/fJ9rUzIMcZQ/hqdefault.jpg",
        "webpage_url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
    }
    return extractor


def test_can_handle():
    from src.services.metadata.search import SearchResolver

    resolver = SearchResolver()
    assert resolver.can_handle("Queen Bohemian Rhapsody") is True
    assert resolver.can_handle("Adele - Rolling in the deep") is True
    # Should not handle commands or URLs
    assert resolver.can_handle("/start") is False
    assert resolver.can_handle("https://open.spotify.com/track/123") is False
    assert resolver.can_handle("https://www.youtube.com/watch?v=123") is False
    assert resolver.can_handle("   ") is False


@pytest.mark.asyncio
async def test_resolve_success(mock_extractor):
    from src.services.metadata.search import SearchResolver

    resolver = SearchResolver(extractor=mock_extractor)
    metadata = await resolver.resolve("Queen Bohemian Rhapsody")

    assert isinstance(metadata, TrackMetadata)
    assert metadata.title == "Bohemian Rhapsody"
    assert metadata.artist == "Queen"
    assert metadata.duration_seconds == 354
    assert metadata.source_url == "https://www.youtube.com/watch?v=fJ9rUzIMcZQ"
    assert metadata.track_id == "yt:fJ9rUzIMcZQ"


@pytest.mark.asyncio
async def test_resolve_fallback_artist_title_parsing():
    from src.services.metadata.search import SearchResolver

    mock_ext = AsyncMock()
    # Simulates yt-dlp returning video title without explicit 'artist' and 'track' fields
    mock_ext.get_metadata_info.return_value = {
        "id": "abc12345",
        "title": "Daft Punk - One More Time",
        "duration": 320,
        "thumbnail": "https://example.com/thumb.jpg",
        "webpage_url": "https://www.youtube.com/watch?v=abc12345",
    }

    resolver = SearchResolver(extractor=mock_ext)
    metadata = await resolver.resolve("Daft Punk One More Time")

    assert metadata.artist == "Daft Punk"
    assert metadata.title == "One More Time"
    assert metadata.duration_seconds == 320


@pytest.mark.asyncio
async def test_resolve_duration_limit_exceeded():
    from src.services.metadata.search import SearchResolver

    mock_ext = AsyncMock()
    mock_ext.get_metadata_info.side_effect = DurationLimitExceededError("Too long")

    resolver = SearchResolver(extractor=mock_ext)
    with pytest.raises(DurationLimitExceededError):
        await resolver.resolve("10 hour ambient mix")


@pytest.mark.asyncio
async def test_resolve_not_found():
    from src.services.metadata.search import SearchResolver

    mock_ext = AsyncMock()
    mock_ext.get_metadata_info.side_effect = TrackNotFoundError("Not found")

    resolver = SearchResolver(extractor=mock_ext)
    with pytest.raises(TrackNotFoundError):
        await resolver.resolve("asdfghjklqwertyuiopnonexistentsong12345")


@pytest.mark.asyncio
async def test_search_candidates_multiple():
    from src.services.metadata.search import SearchResolver

    mock_ext = AsyncMock()
    mock_ext.search_candidates.return_value = [
        {
            "id": "id1",
            "title": "Queen - Bohemian Rhapsody (Official Video)",
            "duration": 360,
            "thumbnail": "https://img/1.jpg",
            "uploader": "Queen Official",
        },
        {
            "id": "id2",
            "title": "Queen - Bohemian Rhapsody (Live Aid 1985)",
            "duration": 165,
            "thumbnail": "https://img/2.jpg",
            "uploader": "Live Aid",
        },
    ]

    resolver = SearchResolver(extractor=mock_ext)
    candidates = await resolver.search_candidates("Queen Bohemian Rhapsody", limit=5)

    assert len(candidates) == 2
    assert candidates[0].track_id == "yt:id1"
    assert candidates[0].artist == "Queen"
    assert candidates[0].title == "Bohemian Rhapsody"
    assert candidates[1].track_id == "yt:id2"
    assert candidates[1].duration_seconds == 165
