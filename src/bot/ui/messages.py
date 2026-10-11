"""UI status strings, error messages, and response formatting helpers."""

from typing import Awaitable, Callable, List, Tuple
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.metadata.base import TrackMetadata

# Command Responses
WELCOME_MESSAGE = (
    "👋 <b>Welcome to Momentum!</b>\n\n"
    "Send a song title and artist, or a direct YouTube video link, to request an MP3.\n\n"
    "<i>Example search:</i> <code>Queen Bohemian Rhapsody</code>\n"
    "<i>Example link:</i> <code>https://www.youtube.com/watch?v=...</code>\n\n"
    "Spotify and YouTube track links are supported. 🎧"
)

HELP_MESSAGE = (
    "📖 <b>How to use this bot:</b>\n\n"
    "• <b>Search by title and artist:</b> Type any song name + artist and I will find matching songs for you to pick.\n"
    "• <b>YouTube Link:</b> Paste standard YouTube, YouTube Music, or youtu.be links.\n\n"
    "• <b>Spotify Track Link:</b> Paste an individual Spotify track URL.\n\n"
    "<b>Constraints:</b>\n"
    "• Maximum track duration: 20 minutes\n"
    "• Maximum file size: 50 MB (Telegram limit)\n"
    "• Full playlists/albums are not supported yet."
)

# Status Update Messages
def msg_searching(query: str) -> str:
    return f"🔍 <b>Searching for:</b> <i>{query}</i>..."

MSG_RESOLVING_SPOTIFY = "🎵 <b>Resolving Spotify track metadata...</b>"
MSG_PROCESSING_YOUTUBE = "🎬 <b>Processing YouTube audio stream...</b>"
MSG_DOWNLOADING = "⬇️ <b>Downloading audio in highest quality (320 kbps)...</b>"
MSG_TAGGING = "🏷️ <b>Embedding metadata and album artwork...</b>"
MSG_UPLOADING = "📤 <b>Uploading MP3 audio to chat...</b>"

STATUS_MESSAGES = {
    "SEARCHING": "🔍 <b>Searching for a matching track...</b>",
    "DOWNLOADING": MSG_DOWNLOADING,
    "CONVERTING": MSG_TAGGING,
    "SENDING": MSG_UPLOADING,
}


def create_status_updater(
    edit_text: Callable[..., Awaitable[object]],
) -> Callable[[str], Awaitable[None]]:
    """Create a callback that updates a Telegram status message by lifecycle stage."""

    async def update(stage: str) -> None:
        text = STATUS_MESSAGES.get(stage.upper(), stage)
        try:
            await edit_text(text=text, parse_mode="HTML")
        except TelegramBadRequest as exc:
            if "message is not modified" not in exc.message.lower():
                raise

    return update

# Error & Boundary Messages
MSG_UNSUPPORTED_BATCH = (
    "⚠️ <b>Batch playlists and albums are currently not supported.</b>\n"
    "Please send an individual track link instead."
)

MSG_DURATION_EXCEEDED = (
    "⏱️ <b>Audio is too long!</b>\n"
    "Maximum allowed duration is 20 minutes."
)

MSG_SIZE_EXCEEDED = (
    "📦 <b>File exceeds limit!</b>\n"
    "This track exceeds Telegram's 50 MB file size limit for bot uploads."
)

MSG_TRACK_NOT_FOUND = (
    "❌ <b>Track not found.</b>\n"
    "Could not find a matching audio track. Please check the spelling or provide a direct link."
)

MSG_STREAM_RESTRICTED = (
    "🔒 <b>Content restricted.</b>\n"
    "This media is private, age-restricted, or geoblocked."
)

MSG_LIVE_STREAM = (
    "📻 <b>Live stream detected.</b>\n"
    "Live streams cannot be converted into MP3 files."
)

MSG_INTERNAL_ERROR = (
    "⚠️ <b>An error occurred while processing your request.</b>\n"
    "Please try again in a few moments."
)


def format_duration(seconds: int) -> str:
    """Formats seconds into mm:ss format."""
    minutes = seconds // 60
    remaining = seconds % 60
    return f"{minutes}:{remaining:02d}"


def create_song_selection_menu(
    query: str, tracks: List[TrackMetadata], query_alias: str = ""
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Constructs an interactive selection message and InlineKeyboardMarkup for candidate tracks.
    """
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    lines = [
        f"🎧 <b>Matching songs for:</b> <i>{query}</i>\n",
        "Select the version you want to download:\n",
    ]

    keyboard_rows: List[List[InlineKeyboardButton]] = []

    for idx, track in enumerate(tracks[:5]):
        emoji = number_emojis[idx] if idx < len(number_emojis) else f"{idx + 1}."
        duration_str = format_duration(track.duration_seconds)

        lines.append(
            f"{emoji} <b>{track.title}</b>\n"
            f"   👤 {track.artist} | ⏱️ {duration_str}\n"
        )

        yt_id = track.track_id.replace("yt:", "")
        btn_label = f"{emoji} {track.title[:25]} ({duration_str})"

        keyboard_rows.append([
            InlineKeyboardButton(
                text=btn_label,
                callback_data=f"dl:{yt_id}:{query_alias}" if query_alias else f"dl:{yt_id}",
            )
        ])

    keyboard_rows.append([
        InlineKeyboardButton(
            text="❌ Cancel",
            callback_data="dl:cancel",
        )
    ])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    text = "\n".join(lines)
    return text, markup
