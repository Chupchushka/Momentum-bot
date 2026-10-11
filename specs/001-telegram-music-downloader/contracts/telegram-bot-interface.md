# Telegram Bot Interface Contract

**Feature**: [spec.md](../spec.md) | **Date**: 2026-10-11 | **Status**: Complete

## 1. Bot Commands

| Command | Description | Response Payload |
| :--- | :--- | :--- |
| `/start` | Initializes conversation and presents usage instructions | Welcome text message explaining how to search songs or send Spotify/YouTube links |
| `/help` | Detailed help instructions and examples | Text message showing query formats and supported link domains |

---

## 2. Message Trigger Contracts

### Input: Text Query (Artist & Title)
- **User sends**: Plain text message (e.g., `Adele - Rolling in the Deep` or `Daft Punk Get Lucky`)
- **Validation**:
  - Length: 3 to 200 characters.
  - Excludes system commands (`/`).
- **Bot Lifecycle Response**:
  1. Status message: `🔍 Searching for "Adele - Rolling in the Deep"...`
  2. Status update: `⬇️ Downloading audio in high quality...`
  3. Final Response: Audio message (`send_audio`):
     - `audio`: MP3 file / Telegram `file_id`
     - `performer`: Resolved artist (e.g. `Adele`)
     - `title`: Resolved title (e.g. `Rolling in the Deep`)
     - `duration`: Track duration in seconds
     - `thumbnail`: Attached album artwork
  4. Status message is deleted upon successful audio delivery.

### Input: Direct Spotify Link
- **User sends**: `https://open.spotify.com/track/{track_id}` or `https://spotify.link/{short_code}`
- **Validation**: Regex matching Spotify track URL scheme.
- **Bot Lifecycle Response**:
  1. Status message: `🎵 Resolving Spotify track...`
  2. Status update: `⬇️ Fetching high-quality stream...`
  3. Final Response: Audio message (`send_audio`) with enriched Spotify metadata and artwork.

### Input: Direct YouTube Link
- **User sends**: `https://www.youtube.com/watch?v={id}`, `https://youtu.be/{id}`, or `https://music.youtube.com/watch?v={id}`
- **Validation**: Regex matching YouTube video or YouTube Music URL scheme.
- **Bot Lifecycle Response**:
  1. Status message: `🎬 Processing YouTube audio stream...`
  2. Status update: `⬇️ Extracting MP3 (best quality)...`
  3. Final Response: Audio message (`send_audio`) with extracted metadata and high-res video thumbnail.

---

## 3. Error and Boundary Responses

| Scenario | User-Facing Message | HTTP / Internal Code |
| :--- | :--- | :--- |
| **Playlist / Album Link** | `⚠️ Batch playlists and albums are currently not supported. Please send an individual track link.` | `UNSUPPORTED_BATCH` |
| **Duration Exceeded** | `⏱️ Audio is too long! Maximum allowed duration is 20 minutes.` | `DURATION_LIMIT_EXCEEDED` |
| **File Size Exceeded** | `📦 File exceeds Telegram's 50 MB upload limit for bots.` | `SIZE_LIMIT_EXCEEDED` |
| **Track Not Found** | `❌ Could not find a matching track. Please check the spelling or provide a direct link.` | `TRACK_NOT_FOUND` |
| **Restricted / Geoblocked** | `🔒 This content is private, age-restricted, or geoblocked.` | `STREAM_RESTRICTED` |
| **Live Stream Link** | `📻 Live streams cannot be converted to MP3.` | `UNSUPPORTED_LIVE_STREAM` |
| **General Error** | `⚠️ An error occurred while processing your request. Please try again later.` | `INTERNAL_ERROR` |
