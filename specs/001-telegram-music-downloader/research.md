# Technical Research: Telegram Music Downloader

**Feature**: [spec.md](spec.md) | **Date**: 2026-10-11 | **Status**: Complete

## 1. Telegram Bot Framework Selection

### Decision
Use **aiogram 3.x** as the primary asynchronous framework for the Telegram bot.

### Rationale
- **Asynchronous Architecture**: Built from the ground up on Python's `asyncio`, enabling non-blocking handling of concurrent user chats, progress updates, and file transfers.
- **Router & Filter Design**: Clean separation of message handlers (text queries vs. link handlers vs. commands) using aiogram routers.
- **Native File Handling**: Supports `FSInputFile` and buffered streams with full Telegram Bot API parameters (`performer`, `title`, `duration`, `thumbnail`).
- **Middleware & State Management**: Supports middleware for rate-limiting, error handling, and session state tracking.

### Alternatives Considered
- *python-telegram-bot*: Traditional and feature-rich, but aiogram 3.x has superior performance for high-throughput async workloads and cleaner router modularity.
- *Telethon / Pyrogram*: Designed primarily for MTProto userbots/client accounts rather than official Bot API tokens.

---

## 2. Audio Extraction & Speed Optimization

### Decision
Use **yt-dlp** via asynchronous subprocess execution (`asyncio.create_subprocess_exec`) paired with **FFmpeg** for audio extraction and transcoding.

### Speed & Quality Optimizations
1. **Audio-Only Stream Extraction**:
   - Format selector: `bestaudio[ext=m4a]/bestaudio/best` to ensure video streams (which consume 80-90% of bandwidth and processing time) are never fetched.
   - Avoid unnecessary network calls: disable playlist extraction (`--no-playlist`), skip certificate checks where safe, and bypass geographic restrictions.
2. **Fast Transcoding**:
   - Direct audio stream conversion to MP3 using FFmpeg with high-quality encoding parameters (`-q:a 0` or `-b:a 320k`).
   - Multi-threaded FFmpeg conversion (`-threads 4`).
3. **Non-Blocking Execution**:
   - Run external downloads and FFmpeg processes through asynchronous subprocesses so the aiogram event loop remains fully responsive.
4. **Bandwidth & Connection Tuning**:
   - Utilize concurrent fragment downloads for segmented streams (`--concurrent-fragments 4`).

### Alternatives Considered
- *pytube*: Highly brittle, frequent breaking changes when YouTube updates its layout, unmaintained.
- *Direct HTTP scraping*: Fragile and easily blocked by rate-limiting or signature ciphering.

---

## 3. Spotify Track Resolution Strategy

### Decision
Extract Spotify track metadata via **Spotipy** (or lightweight direct Spotify Web API requests with Client Credentials) and resolve to high-fidelity audio streams.

### Rationale
- Spotify streams are protected by DRM encryption and cannot be directly extracted as MP3 without DRM circumvention.
- The standard industry pattern for Telegram music bots:
  1. Parse the Spotify URL to obtain the Spotify Track ID.
  2. Query Spotify's metadata endpoint to retrieve exact track metadata: `title`, `artist(s)`, `album`, `duration`, and high-resolution `album cover image URL`.
  3. Formulate an exact audio query (e.g., `"{artist} - {title} Official Audio"`) on public streaming services (YouTube / YouTube Music) to locate the exact match.
  4. Verify matching duration within a ±5 second tolerance to avoid selecting live versions or karaoke tracks.

### Alternatives Considered
- *Direct scraping of open.spotify.com embed pages*: Eliminates need for Spotify API credentials but is prone to HTML structure changes and rate limits.
- *Preview-only extraction*: Spotify API provides 30-second preview clips, but users demand the full song.

---

## 4. Metadata Tagging & Presentation

### Decision
Use **Mutagen** for embedding comprehensive ID3 tags (ID3v2.4) and high-resolution album artwork into the output MP3 file.

### Metadata Pipeline
1. Download track cover artwork asynchronously via `aiohttp`.
2. Extract or resolve tags:
   - `TIT2`: Track Title
   - `TPE1`: Artist / Performer
   - `TALB`: Album Name
   - `APIC`: Cover Art (MIME type `image/jpeg` or `image/png`)
   - `TLEN`: Duration in milliseconds
3. Deliver the MP3 via `bot.send_audio()` using parameters:
   - `audio`: `FSInputFile(file_path)`
   - `title`: Track Title
   - `performer`: Artist Name
   - `duration`: Track Duration in seconds
   - `thumbnail`: `FSInputFile(thumbnail_path)`

### Rationale
Telegram's native music player relies on both the API parameters (`performer`, `title`) and the embedded ID3 tags within the MP3 container for persistent offline playback and playlist display.

---

## 5. Instant Response & Delivery Optimization: Telegram File ID Caching

### Decision
Implement a lightweight local metadata & **Telegram `file_id` Cache** (SQLite or key-value store).

### Rationale
- When the bot sends an audio file to Telegram, the Telegram API response includes a unique `file_id`.
- If a user (or another user) requests the same track or link again, the bot immediately calls `bot.send_audio(chat_id, audio=cached_file_id)`.
- **Result**: Zero download, zero transcode, zero upload. Delivery happens in **< 1 second**, conserving server bandwidth and compute resources.

### Cache Key Structure
- Spotify Track: `spotify:{track_id}`
- YouTube Video: `youtube:{video_id}`
- Text Search: Normalized lowercase query `search:{normalized_artist_title}`

---

## 6. Concurrency & Resource Safeguards

### Decision
Enforce a semaphore-bounded asynchronous queue:
- **Concurrency Limit**: Max 3-5 concurrent downloads running simultaneously to avoid CPU/network starvation.
- **Duration Cap**: Reject videos/tracks exceeding 20 minutes (prevents multi-hour podcasts or mixes from consuming resources).
- **Size Cap**: Validate that generated MP3 files remain under 50 MB (Telegram Bot API limit).
- **Ephemeral Storage**: All temporary audio and image files are stored in a dedicated temporary directory (`/tmp/music_bot/...`) and unlinked in a `finally` block immediately after dispatch.
