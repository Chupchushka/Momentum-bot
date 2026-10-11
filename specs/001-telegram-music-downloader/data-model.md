# Data Model: Telegram Music Downloader

**Feature**: [spec.md](spec.md) | **Date**: 2026-10-11 | **Status**: Complete

## 1. Entities

### UserRequest
Represents an incoming interaction from a Telegram user.

| Field | Type | Description | Validation |
| :--- | :--- | :--- | :--- |
| `request_id` | UUID / str | Unique identifier for the user request | Auto-generated UUID4 |
| `user_id` | int | Telegram User ID | Must be positive integer |
| `chat_id` | int | Telegram Chat ID for dispatching responses | Integer |
| `message_id` | int | Original message ID for replies / status updates | Integer |
| `raw_input` | str | Raw text query or pasted URL | Non-empty, max 500 characters |
| `request_type` | Enum | `TEXT_SEARCH`, `SPOTIFY_URL`, `YOUTUBE_URL`, `UNSUPPORTED` | Must match recognized enum |
| `created_at` | datetime | Timestamp of request creation | ISO 8601 UTC |

### TrackMetadata
Represents the normalized metadata for a musical track across all supported sources.

| Field | Type | Description | Validation |
| :--- | :--- | :--- | :--- |
| `track_id` | str | Normalized identifier (e.g., `sp:4cOdK2wGslZ5eOSY...` or `yt:dQw4w9WgXcQ`) | Required, non-empty |
| `title` | str | Track title | Non-empty, max 200 characters |
| `artist` | str | Primary artist or comma-separated artists | Non-empty, max 200 characters |
| `album` | Optional[str] | Album title | Optional, max 200 characters |
| `duration_seconds` | int | Expected duration of the audio in seconds | Positive integer, <= 1200 (20 min) |
| `cover_art_url` | Optional[str] | URL to high-resolution album cover artwork | Valid HTTP/HTTPS URL |
| `source_url` | str | Canonical URL of the source | Valid URL |

### AudioDeliverable
Represents the processed MP3 audio file ready for transmission to Telegram.

| Field | Type | Description | Validation |
| :--- | :--- | :--- | :--- |
| `file_path` | Path | Local absolute path to the generated MP3 file | Must exist on filesystem prior to upload |
| `cover_path` | Optional[Path]| Local path to downloaded album thumbnail | Must exist if provided |
| `file_size_bytes` | int | File size in bytes | Must be > 0 and <= 52,428,800 (50 MB) |
| `bitrate_kbps` | int | Audio bitrate in kbps | Standard range: 128 to 320 kbps |
| `duration_seconds` | int | Measured duration in seconds | Must match source within 5% tolerance |
| `format` | str | Audio format container | Must strictly equal `mp3` |

### CachedTrack
Represents a previously delivered audio track stored to enable instantaneous responses.

| Field | Type | Description | Validation |
| :--- | :--- | :--- | :--- |
| `cache_key` | str | Unique normalized hash or identifier | Format: `spotify:{id}`, `youtube:{id}`, or `search:{norm}` |
| `telegram_file_id`| str | Telegram-assigned file identifier for fast re-send | Non-empty string |
| `title` | str | Title of the track | Non-empty string |
| `artist` | str | Artist of the track | Non-empty string |
| `duration_seconds`| int | Duration in seconds | Positive integer |
| `created_at` | datetime | When this entry was cached | ISO 8601 UTC |
| `hit_count` | int | Number of times this cached track was served | >= 0 |

---

## 2. State Transitions (Download Lifecycle)

```
[User Message Received]
          │
          ▼
   [PARSING_INPUT] ──(Invalid/Unsupported)──► [REJECTED] ──► (Send Error Message)
          │
      (Valid)
          │
          ▼
   [CHECKING_CACHE] ──(Cache Hit)──────────► [FAST_DISPATCH] ──► (Send via file_id)
          │                                                          │
     (Cache Miss)                                                    │
          │                                                          ▼
          ▼                                                      [COMPLETED]
   [RESOLVING_METADATA]
          │
          ▼
   [EXTRACTING_AUDIO]
          │
          ▼
   [TAGGING_METADATA]
          │
          ▼
   [UPLOADING_FILE] ──► [CACHING_FILE_ID] ──► [CLEANING_TEMP] ──► [COMPLETED]
          │
     (Any Failure)
          │
          ▼
   [FAILED] ──► [CLEANING_TEMP] ──► (Send User-Friendly Error)
```

---

## 3. Validation Rules

1. **Duration Constraint**: Any track whose detected duration exceeds 1,200 seconds (20 minutes) must be immediately aborted before full audio extraction to prevent resource hogging.
2. **File Size Constraint**: If the resulting MP3 file exceeds 50 MB, the upload cannot proceed through the standard Telegram Bot API. The bot must delete the file and notify the user.
3. **Storage Hygiene**: Every file in `AudioDeliverable` must be guaranteed to be removed in a `finally` block or context manager after upload completion or error.
