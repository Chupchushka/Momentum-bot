"""Direct YouTube and Spotify link handling with Telegram file ID caching."""

import re

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, Message

from src.bot.ui.messages import (
    MSG_DURATION_EXCEEDED,
    MSG_INTERNAL_ERROR,
    MSG_SIZE_EXCEEDED,
    MSG_TRACK_NOT_FOUND,
    create_status_updater,
)
from src.services.audio.extractor import (
    DurationLimitExceededError,
    FileSizeExceededError,
    TrackNotFoundError,
)
from src.services.audio.pipeline import get_audio_pipeline
from src.services.cache.repository import CachedTrack

router = Router(name="links")
_YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})",
    re.IGNORECASE,
)
_SPOTIFY_TRACK = re.compile(r"open\.spotify\.com/track/([A-Za-z0-9]+)", re.IGNORECASE)


def _cache_key(raw_input: str) -> str | None:
    youtube = _YOUTUBE_ID.search(raw_input)
    if youtube:
        return f"youtube:{youtube.group(1)}"
    spotify = _SPOTIFY_TRACK.search(raw_input)
    if spotify:
        return f"spotify:{spotify.group(1)}"
    return None


@router.message(F.text, lambda message: bool(_cache_key((message.text or "").strip())))
async def handle_direct_link(message: Message) -> None:
    """Serve cached links immediately or process and cache the resulting audio."""
    raw_input = (message.text or "").strip()
    key = _cache_key(raw_input)
    if not key:
        return

    pipeline = get_audio_pipeline()
    status = await message.reply("🎵 <b>Processing audio link...</b>", parse_mode=ParseMode.HTML)
    deliverable = None
    update_status = create_status_updater(status.edit_text)

    try:
        cached = pipeline.cache_repo.get(key)
        if cached:
            await message.bot.send_audio(
                chat_id=message.chat.id,
                audio=cached.telegram_file_id,
                title=cached.title,
                performer=cached.artist,
                duration=cached.duration_seconds,
            )
            await status.delete()
            return

        deliverable, metadata = await pipeline.process_request(
            raw_input,
            status_callback=update_status,
        )
        await update_status("SENDING")
        sent = await message.bot.send_audio(
            chat_id=message.chat.id,
            audio=FSInputFile(str(deliverable.file_path)),
            title=metadata.title,
            performer=metadata.artist,
            duration=metadata.duration_seconds,
            thumbnail=(
                FSInputFile(str(deliverable.cover_path))
                if deliverable.cover_path and deliverable.cover_path.exists()
                else None
            ),
        )
        file_id = getattr(getattr(sent, "audio", None), "file_id", None)
        if file_id:
            pipeline.cache_repo.put(
                CachedTrack(
                    cache_key=key,
                    telegram_file_id=file_id,
                    title=metadata.title,
                    artist=metadata.artist,
                    duration_seconds=metadata.duration_seconds,
                )
            )
        await status.delete()
    except TrackNotFoundError:
        await status.edit_text(MSG_TRACK_NOT_FOUND, parse_mode=ParseMode.HTML)
    except DurationLimitExceededError:
        await status.edit_text(MSG_DURATION_EXCEEDED, parse_mode=ParseMode.HTML)
    except FileSizeExceededError:
        await status.edit_text(MSG_SIZE_EXCEEDED, parse_mode=ParseMode.HTML)
    except Exception:
        await status.edit_text(MSG_INTERNAL_ERROR, parse_mode=ParseMode.HTML)
    finally:
        if deliverable:
            pipeline.cleanup_deliverable(deliverable)
