"""Contract coverage for fast link cache delivery and cache population."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.handlers import links
from src.bot.handlers import search
from src.services.cache.repository import CachedTrack
from src.services.metadata.base import TrackMetadata


def _message(tmp_path: Path):
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    sent_audio = SimpleNamespace(audio=SimpleNamespace(file_id="telegram-file-id"))
    bot = SimpleNamespace(send_audio=AsyncMock(return_value=sent_audio))
    message = SimpleNamespace(
        text="https://youtu.be/abcdefghijk",
        chat=SimpleNamespace(id=123),
        bot=bot,
        reply=AsyncMock(return_value=status),
    )
    return message, status, bot


@pytest.mark.asyncio
async def test_cached_youtube_link_is_resent_without_processing(monkeypatch, tmp_path):
    message, status, bot = _message(tmp_path)
    cached = CachedTrack(
        cache_key="youtube:abcdefghijk",
        telegram_file_id="cached-file-id",
        title="Song",
        artist="Artist",
        duration_seconds=180,
    )
    pipeline = SimpleNamespace(
        cache_repo=SimpleNamespace(get=MagicMock(return_value=cached)),
        process_request=AsyncMock(),
        cleanup_deliverable=MagicMock(),
    )
    monkeypatch.setattr(links, "get_audio_pipeline", lambda: pipeline)

    await links.handle_direct_link(message)

    bot.send_audio.assert_awaited_once_with(
        chat_id=123,
        audio="cached-file-id",
        title="Song",
        performer="Artist",
        duration=180,
    )
    pipeline.process_request.assert_not_awaited()
    status.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_link_delivery_is_cached(monkeypatch, tmp_path):
    message, status, bot = _message(tmp_path)
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"audio")
    metadata = TrackMetadata(
        track_id="yt:abcdefghijk",
        title="Song",
        artist="Artist",
        duration_seconds=180,
        source_url="https://youtube.com/watch?v=abcdefghijk",
    )
    deliverable = SimpleNamespace(file_path=mp3, cover_path=None)
    cache_repo = SimpleNamespace(get=MagicMock(return_value=None), put=MagicMock())
    pipeline = SimpleNamespace(
        cache_repo=cache_repo,
        process_request=AsyncMock(return_value=(deliverable, metadata)),
        cleanup_deliverable=MagicMock(),
    )
    monkeypatch.setattr(links, "get_audio_pipeline", lambda: pipeline)

    await links.handle_direct_link(message)

    cache_repo.put.assert_called_once()
    stored = cache_repo.put.call_args.args[0]
    assert stored.cache_key == "youtube:abcdefghijk"
    assert stored.telegram_file_id == "telegram-file-id"
    pipeline.cleanup_deliverable.assert_called_once_with(deliverable)
    status.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_spotify_link_is_not_sent_through_another_audio_source(monkeypatch, tmp_path):
    message, status, _bot = _message(tmp_path)
    message.text = "https://open.spotify.com/track/AbCd1234"
    cache_get = MagicMock()
    pipeline = SimpleNamespace(
        cache_repo=SimpleNamespace(get=cache_get),
        process_request=AsyncMock(),
        cleanup_deliverable=MagicMock(),
    )
    monkeypatch.setattr(links, "get_audio_pipeline", lambda: pipeline)

    await links.handle_direct_link(message)

    cache_get.assert_not_called()
    pipeline.process_request.assert_not_awaited()
    status.edit_text.assert_awaited_once()
    assert "cannot be downloaded directly" in status.edit_text.await_args.args[0]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://youtu.be/abcdefghijk", "youtube:abcdefghijk"),
        ("https://open.spotify.com/track/AbCd1234", "spotify:AbCd1234"),
    ],
)
def test_link_cache_key_identifies_supported_track_urls(url, expected):
    assert links._cache_key(url) == expected


@pytest.mark.asyncio
async def test_cached_text_search_is_resent_without_searching(monkeypatch):
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    bot = SimpleNamespace(send_audio=AsyncMock())
    message = SimpleNamespace(
        text="Queen Bohemian Rhapsody",
        from_user=SimpleNamespace(id=7),
        chat=SimpleNamespace(id=123),
        bot=bot,
        reply=AsyncMock(return_value=status),
    )
    cached = CachedTrack(
        cache_key="search:bohemian_queen_rhapsody",
        telegram_file_id="cached-search-file",
        title="Bohemian Rhapsody",
        artist="Queen",
        duration_seconds=354,
    )
    pipeline = SimpleNamespace(
        cache_repo=SimpleNamespace(get=MagicMock(return_value=cached)),
        search_candidates=AsyncMock(),
    )
    monkeypatch.setattr(search, "get_audio_pipeline", lambda: pipeline)

    await search.handle_text_search(message)

    bot.send_audio.assert_awaited_once()
    assert bot.send_audio.await_args.kwargs["audio"] == "cached-search-file"
    pipeline.search_candidates.assert_not_awaited()
    status.delete.assert_awaited_once()
