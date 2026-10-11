"""Contract tests for search handler and interactive selection menu."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import CallbackQuery, Chat, Message, User
from src.services.metadata.base import AudioDeliverable, TrackMetadata
from src.services.audio.extractor import DurationLimitExceededError, TrackNotFoundError
from src.bot.ui.messages import MSG_DURATION_EXCEEDED, MSG_TRACK_NOT_FOUND


@pytest.fixture
def dummy_message(tmp_path: Path):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 123456
    message.message_id = 99
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456
    message.text = "Queen Bohemian Rhapsody"

    status_msg = MagicMock(spec=Message)
    status_msg.message_id = 100
    status_msg.edit_text = AsyncMock()
    status_msg.delete = AsyncMock()

    message.reply = AsyncMock(return_value=status_msg)
    message.answer = AsyncMock(return_value=status_msg)
    message.answer_audio = AsyncMock()

    bot = AsyncMock()
    bot.send_audio = AsyncMock()
    message.bot = bot

    return message, status_msg


@pytest.mark.asyncio
async def test_search_handler_single_result_direct_send(dummy_message, tmp_path: Path):
    from src.bot.handlers.search import handle_text_search

    message, status_msg = dummy_message

    audio_file = tmp_path / "song.mp3"
    audio_file.write_bytes(b"dummy mp3 data")

    deliverable = AudioDeliverable(
        file_path=audio_file,
        file_size_bytes=len(b"dummy mp3 data"),
        bitrate_kbps=320,
        duration_seconds=354,
        format="mp3",
    )
    metadata = TrackMetadata(
        track_id="yt:test1234",
        title="Bohemian Rhapsody",
        artist="Queen",
        duration_seconds=354,
        source_url="https://youtube.com/watch?v=test1234",
    )

    mock_pipeline = AsyncMock()
    mock_pipeline.cleanup_deliverable = MagicMock()
    mock_pipeline.search_candidates.return_value = [metadata]
    mock_pipeline.process_request.return_value = (deliverable, metadata)

    with patch("src.bot.handlers.search.get_audio_pipeline", return_value=mock_pipeline):
        await handle_text_search(message)

    # Verifies initial status reply was sent
    message.reply.assert_awaited_once()

    # Verifies audio was sent
    message.bot.send_audio.assert_awaited_once()
    send_audio_kwargs = message.bot.send_audio.call_args[1]
    assert send_audio_kwargs["title"] == "Bohemian Rhapsody"
    assert send_audio_kwargs["performer"] == "Queen"
    assert send_audio_kwargs["duration"] == 354


@pytest.mark.asyncio
async def test_search_handler_multiple_results_shows_menu(dummy_message):
    from src.bot.handlers.search import handle_text_search

    message, status_msg = dummy_message

    m1 = TrackMetadata(
        track_id="yt:id1",
        title="Bohemian Rhapsody (Studio)",
        artist="Queen",
        duration_seconds=354,
        source_url="https://youtube.com/watch?v=id1",
    )
    m2 = TrackMetadata(
        track_id="yt:id2",
        title="Bohemian Rhapsody (Live)",
        artist="Queen",
        duration_seconds=320,
        source_url="https://youtube.com/watch?v=id2",
    )

    mock_pipeline = AsyncMock()
    mock_pipeline.search_candidates.return_value = [m1, m2]

    with patch("src.bot.handlers.search.get_audio_pipeline", return_value=mock_pipeline):
        await handle_text_search(message)

    # Verifies status message was updated with inline keyboard menu
    status_msg.edit_text.assert_awaited_once()
    kwargs = status_msg.edit_text.call_args.kwargs
    assert "reply_markup" in kwargs
    assert len(kwargs["reply_markup"].inline_keyboard) == 3  # 2 songs + Cancel


@pytest.mark.asyncio
async def test_callback_selection_downloads_song(tmp_path: Path):
    from src.bot.handlers.search import handle_song_selection_callback

    call = MagicMock(spec=CallbackQuery)
    call.data = "dl:PadKCVBIN94"
    call.from_user = MagicMock(spec=User)
    call.from_user.id = 123456
    call.answer = AsyncMock()

    status_msg = MagicMock(spec=Message)
    status_msg.edit_text = AsyncMock()
    status_msg.delete = AsyncMock()
    status_msg.chat = MagicMock(spec=Chat)
    status_msg.chat.id = 123456

    call.message = status_msg
    bot = AsyncMock()
    bot.send_audio = AsyncMock()
    call.bot = bot

    audio_file = tmp_path / "song.mp3"
    audio_file.write_bytes(b"dummy mp3 data")

    deliverable = AudioDeliverable(
        file_path=audio_file,
        file_size_bytes=len(b"dummy mp3 data"),
        bitrate_kbps=320,
        duration_seconds=316,
        format="mp3",
    )
    metadata = TrackMetadata(
        track_id="yt:PadKCVBIN94",
        title="Bohemian Rhapsody 1981 Live",
        artist="Queen",
        duration_seconds=316,
        source_url="https://youtube.com/watch?v=PadKCVBIN94",
    )

    mock_pipeline = AsyncMock()
    mock_pipeline.cleanup_deliverable = MagicMock()
    mock_pipeline.process_request.return_value = (deliverable, metadata)

    with patch("src.bot.handlers.search.get_audio_pipeline", return_value=mock_pipeline):
        await handle_song_selection_callback(call)

    call.answer.assert_awaited_once()
    bot.send_audio.assert_awaited_once()
    send_audio_kwargs = bot.send_audio.call_args[1]
    assert send_audio_kwargs["title"] == "Bohemian Rhapsody 1981 Live"
    assert send_audio_kwargs["performer"] == "Queen"


@pytest.mark.asyncio
async def test_search_handler_track_not_found(dummy_message):
    from src.bot.handlers.search import handle_text_search

    message, status_msg = dummy_message

    mock_pipeline = AsyncMock()
    mock_pipeline.search_candidates.side_effect = TrackNotFoundError("Not found")

    with patch("src.bot.handlers.search.get_audio_pipeline", return_value=mock_pipeline):
        await handle_text_search(message)

    status_msg.edit_text.assert_awaited_once()
    called_text = status_msg.edit_text.call_args.kwargs.get("text") or status_msg.edit_text.call_args.args[0]
    assert MSG_TRACK_NOT_FOUND in called_text


@pytest.mark.asyncio
async def test_search_handler_duration_exceeded(dummy_message):
    from src.bot.handlers.search import handle_text_search

    message, status_msg = dummy_message

    mock_pipeline = AsyncMock()
    mock_pipeline.search_candidates.side_effect = DurationLimitExceededError("Too long")

    with patch("src.bot.handlers.search.get_audio_pipeline", return_value=mock_pipeline):
        await handle_text_search(message)

    status_msg.edit_text.assert_awaited_once()
    called_text = status_msg.edit_text.call_args.kwargs.get("text") or status_msg.edit_text.call_args.args[0]
    assert MSG_DURATION_EXCEEDED in called_text
