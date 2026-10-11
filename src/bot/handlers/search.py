"""Handler for natural language text search queries and interactive song selection menu."""

import inspect
import re
from typing import Any, Optional

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, FSInputFile, Message

from src.bot.ui.messages import (
    MSG_DOWNLOADING,
    MSG_DURATION_EXCEEDED,
    MSG_INTERNAL_ERROR,
    MSG_SIZE_EXCEEDED,
    MSG_TRACK_NOT_FOUND,
    create_song_selection_menu,
    create_status_updater,
    msg_searching,
)
from src.core.logging import get_logger
from src.services.audio.extractor import (
    AudioExtractionError,
    DurationLimitExceededError,
    FileSizeExceededError,
    TrackNotFoundError,
)
from src.services.audio.pipeline import get_audio_pipeline
from src.services.cache.repository import CacheRepository, CachedTrack

logger = get_logger("handlers.search")
router = Router(name="search")


async def _maybe_await(value: Any) -> Any:
    """Allow real synchronous repositories and async test doubles."""
    return await value if inspect.isawaitable(value) else value


def is_plain_search_query(message: Message) -> bool:
    """Filter ensuring text is not a command and not a direct web URL."""
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return False
    # If it looks like a URL, let the links handler process it
    if re.match(r"^(https?://|www\.|spotify:)", text, re.IGNORECASE):
        return False
    return True


@router.message(F.text, is_plain_search_query)
async def handle_text_search(message: Message) -> None:
    """
    Searches for song candidates and presents an interactive inline menu
    allowing the user to select the exact version they want.
    """
    query = (message.text or "").strip()
    logger.info(
        "Received search query from user %s: '%s'",
        message.from_user.id if message.from_user else "unknown",
        query,
    )

    status_msg = await message.reply(
        text=msg_searching(query),
        parse_mode=ParseMode.HTML,
    )

    pipeline = get_audio_pipeline()

    try:
        search_cache_key = CacheRepository.normalize_query_key(query)
        cached = await _maybe_await(pipeline.cache_repo.get(search_cache_key))
        if not isinstance(cached, CachedTrack):
            cached = None
        if cached:
            await message.bot.send_audio(
                chat_id=message.chat.id,
                audio=cached.telegram_file_id,
                title=cached.title,
                performer=cached.artist,
                duration=cached.duration_seconds,
            )
            await status_msg.delete()
            return

        candidates = await pipeline.search_candidates(query, limit=5)
        if not candidates:
            await status_msg.edit_text(
                text=MSG_TRACK_NOT_FOUND,
                parse_mode=ParseMode.HTML,
            )
            return

        # If exactly 1 result was found, download and send directly
        if len(candidates) == 1:
            track = candidates[0]
            await _download_and_send_track(
                chat_id=message.chat.id,
                bot=message.bot,
                source_url=track.source_url,
                status_message=status_msg,
                cache_key=search_cache_key,
            )
            return

        # Multiple candidates found: display interactive selection menu
        alias = CacheRepository.query_alias(search_cache_key)
        await _maybe_await(pipeline.cache_repo.put_alias(alias, search_cache_key))
        menu_text, markup = create_song_selection_menu(query, candidates, query_alias=alias)
        await status_msg.edit_text(
            text=menu_text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )

    except TrackNotFoundError:
        await status_msg.edit_text(
            text=MSG_TRACK_NOT_FOUND,
            parse_mode=ParseMode.HTML,
        )
    except DurationLimitExceededError:
        await status_msg.edit_text(
            text=MSG_DURATION_EXCEEDED,
            parse_mode=ParseMode.HTML,
        )
    except FileSizeExceededError:
        await status_msg.edit_text(text=MSG_SIZE_EXCEEDED, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Error searching candidates for '%s': %s", query, exc)
        await status_msg.edit_text(
            text=MSG_INTERNAL_ERROR,
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data.startswith("dl:"))
async def handle_song_selection_callback(call: CallbackQuery) -> None:
    """Handles button clicks on the interactive song selection menu."""
    data = call.data or ""

    if data == "dl:cancel":
        await call.answer("Cancelled")
        if call.message and isinstance(call.message, Message):
            await call.message.edit_text(
                text="❌ <b>Search cancelled.</b>",
                parse_mode=ParseMode.HTML,
            )
        return

    _, yt_id, *alias_parts = data.split(":", maxsplit=2)
    query_cache_key = None
    if alias_parts:
        pipeline = get_audio_pipeline()
        query_cache_key = await _maybe_await(pipeline.cache_repo.get_alias(alias_parts[0]))
        if not isinstance(query_cache_key, str):
            query_cache_key = None
    source_url = f"https://www.youtube.com/watch?v={yt_id}"

    await call.answer("Downloading selected song...")
    logger.info("User selected track ID: %s for download", yt_id)

    status_msg = call.message if isinstance(call.message, Message) else None
    if status_msg:
        await status_msg.edit_text(
            text=MSG_DOWNLOADING,
            parse_mode=ParseMode.HTML,
        )

    await _download_and_send_track(
        chat_id=call.message.chat.id if call.message else call.from_user.id,
        bot=call.bot,
        source_url=source_url,
        status_message=status_msg,
        cache_key=query_cache_key or f"youtube:{yt_id}",
    )


async def _download_and_send_track(
    chat_id: int,
    bot,
    source_url: str,
    status_message: Optional[Message] = None,
    cache_key: Optional[str] = None,
) -> None:
    """Downloads audio for a source URL and delivers the MP3 to the chat."""
    pipeline = get_audio_pipeline()
    deliverable = None

    update_status = create_status_updater(status_message.edit_text) if status_message else None

    try:
        if cache_key:
            cached = await _maybe_await(pipeline.cache_repo.get(cache_key))
            if not isinstance(cached, CachedTrack):
                cached = None
            if cached:
                await bot.send_audio(
                    chat_id=chat_id,
                    audio=cached.telegram_file_id,
                    title=cached.title,
                    performer=cached.artist,
                    duration=cached.duration_seconds,
                )
                if status_message:
                    await status_message.delete()
                return

        deliverable, metadata = await pipeline.process_request(
            raw_input=source_url,
            status_callback=update_status,
        )

        audio_file = FSInputFile(str(deliverable.file_path))
        thumbnail_file = (
            FSInputFile(str(deliverable.cover_path))
            if deliverable.cover_path and deliverable.cover_path.exists()
            else None
        )

        if update_status:
            await update_status("SENDING")
        sent_message = await bot.send_audio(
            chat_id=chat_id,
            audio=audio_file,
            title=metadata.title,
            performer=metadata.artist,
            duration=metadata.duration_seconds,
            thumbnail=thumbnail_file,
        )

        if cache_key:
            audio = getattr(sent_message, "audio", None)
            file_id = getattr(audio, "file_id", None)
            if file_id:
                await _maybe_await(pipeline.cache_repo.put(CachedTrack(
                    cache_key=cache_key,
                    telegram_file_id=file_id,
                    title=metadata.title,
                    artist=metadata.artist,
                    duration_seconds=metadata.duration_seconds,
                )))

        if status_message:
            try:
                await status_message.delete()
            except Exception:
                pass

    except TrackNotFoundError:
        if status_message:
            await status_message.edit_text(
                text=MSG_TRACK_NOT_FOUND,
                parse_mode=ParseMode.HTML,
            )
    except DurationLimitExceededError:
        if status_message:
            await status_message.edit_text(
                text=MSG_DURATION_EXCEEDED,
                parse_mode=ParseMode.HTML,
            )
    except FileSizeExceededError:
        if status_message:
            await status_message.edit_text(text=MSG_SIZE_EXCEEDED, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Error processing download for %s: %s", source_url, exc)
        if status_message:
            await status_message.edit_text(
                text=MSG_INTERNAL_ERROR,
                parse_mode=ParseMode.HTML,
            )
    finally:
        if deliverable:
            pipeline.cleanup_deliverable(deliverable)
