# Quickstart & Validation Guide: Telegram Music Downloader

**Feature**: [spec.md](spec.md) | **Date**: 2026-10-11 | **Status**: Complete

This guide details prerequisites, local environment configuration, and end-to-end test scenarios to validate the Telegram Music Downloader bot.

---

## 1. Prerequisites

- **Python**: Version 3.11 or newer
- **FFmpeg**: Installed and available in system `$PATH` (`ffmpeg -version`)
- **Telegram Bot Token**: Obtained from [@BotFather](https://t.me/BotFather)
- **Spotify API Credentials** (Optional for enhanced metadata): Client ID & Client Secret from Spotify Developer Dashboard

---

## 2. Environment Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables (.env)
cp .env.example .env
# Edit .env and supply:
# TELEGRAM_BOT_TOKEN="your_bot_token_here"
# SPOTIFY_CLIENT_ID="your_spotify_id"        (optional)
# SPOTIFY_CLIENT_SECRET="your_spotify_secret" (optional)
```

---

## 3. Running the Bot

```bash
# Start the bot locally in long-polling mode
python -m src.main
```

Expected startup log:
```text
INFO:aiogram.dispatcher:Starting polling...
INFO:src.main:Telegram Music Downloader started successfully.
```

---

## 4. End-to-End Validation Scenarios

### Scenario 1: Search by Artist and Title (Text Query)
1. Open Telegram and navigate to the bot chat.
2. Send message: `Daft Punk One More Time`
3. **Verify**:
   - Bot sends temporary status: `🔍 Searching for "Daft Punk One More Time"...`
   - Status transitions to `⬇️ Downloading audio...`
   - Bot delivers an MP3 audio file.
   - Playing the audio in Telegram displays:
     - Title: `One More Time`
     - Performer: `Daft Punk`
     - Embedded album cover image.

### Scenario 2: Direct Spotify Track URL
1. In Telegram, send message: `https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b`
2. **Verify**:
   - Bot acknowledges with Spotify resolution status.
   - Bot delivers the matching MP3 file with high-quality audio and original album artwork.

### Scenario 3: Direct YouTube Video URL
1. In Telegram, send message: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
2. **Verify**:
   - Bot extracts audio stream at highest bitrate.
   - Delivers .mp3 file with video title, artist/channel name, and thumbnail.

### Scenario 4: Fast Cache Delivery
1. Send the same query or URL again from Scenario 1 or 2.
2. **Verify**:
   - Delivery completes almost instantaneously (< 1.5 seconds) via Telegram `file_id` cache hit without invoking FFmpeg or downloading audio from external networks.

### Scenario 5: Edge Case - Oversized Media / Playlist
1. Send a YouTube playlist URL or a multi-hour video link.
2. **Verify**:
   - Bot responds within 3 seconds with a clean error message explaining playlists or oversized files are not supported.
   - No zombie files remain in the temporary directory.

---

## 5. Automated Test Suite Execution

```bash
# Run unit and contract tests
pytest tests/unit tests/contract -v

# Run integration tests (requires active internet connection)
pytest tests/integration -v -m "not e2e"
```
