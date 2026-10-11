# Implementation Plan: Telegram Music Downloader

**Branch**: `001-telegram-music-downloader` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-telegram-music-downloader/spec.md`

## Summary

Build an asynchronous Telegram music downloader bot in Python using **aiogram 3.x**. The system allows users to download music by either typing a song title and artist or pasting direct Spotify/YouTube links. The technical design prioritizes **maximum audio quality** (up to 320 kbps MP3 with full ID3 metadata and embedded cover art) and **maximum download speed** (audio-only stream extraction via `yt-dlp`, multi-threaded FFmpeg transcoding, asynchronous non-blocking pipelines, and Telegram `file_id` caching for instantaneous repeat deliveries).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- `aiogram` (v3.x): High-performance asynchronous Telegram bot framework.
- `yt-dlp`: High-speed audio extraction directly targeting audio-only streams (`ba/b`).
- `ffmpeg`: System-level binary for fast audio stream extraction and MP3 transcoding at 320 kbps.
- `mutagen`: ID3v2.4 tag and album artwork embedding.
- `aiohttp`: Asynchronous HTTP client for fetching remote album art and Spotify Open Graph/API metadata.
- `pydantic` & `pydantic-settings`: Strongly typed environment and bot configuration.

**Storage**:
- Ephemeral filesystem storage (`/tmp/music_bot_tmp`) with guaranteed cleanup post-upload.
- SQLite (`cache.db`) for storing resolved metadata and Telegram `file_id` references for instant re-sends.

**Testing**: `pytest`, `pytest-asyncio`

**Target Platform**: Linux server / macOS / Docker container

**Project Type**: Async Telegram Bot daemon / CLI

**Performance Goals**:
- < 1 second initial response acknowledging user input.
- < 30 seconds end-to-end download, transcode, and upload for standard tracks (< 5 minutes).
- < 1.5 seconds delivery time for cached tracks using Telegram `file_id`.
- Highest possible audio fidelity (320 kbps MP3 target).

**Constraints**:
- Max file size: 50 MB (standard Telegram Bot API limit).
- Max track duration: 20 minutes (prevents abuse / memory exhaustion).
- Zero zombie file leakage: all temporary files cleaned up in `finally` blocks.
- Concurrency limit: Semaphore bounded to 4 concurrent audio extractions.

**Scale/Scope**: Single-track fetching for Telegram chats and groups.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Simplicity**: Single clean project structure with decoupled services (handlers, metadata, audio extractor, cache).
- **Test-First**: Unit tests for resolvers and contracts; mock-based tests for Telegram handlers; integration tests for audio pipelines.
- **Observability**: Structured logging for all download jobs, cache hits/misses, and error events.
- **Result**: PASSED. No gates violated.

## Project Structure

### Documentation (this feature)

```text
specs/001-telegram-music-downloader/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical research & architecture decisions
├── data-model.md        # Entities, validation rules, state transitions
├── quickstart.md        # Validation guide and run instructions
├── contracts/           # Component and bot interface contracts
│   ├── telegram-bot-interface.md
│   └── audio-pipeline-contract.md
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (repository root)

```text
src/
├── __init__.py
├── main.py                  # Bot entrypoint and dispatcher lifecycle
├── core/
│   ├── __init__.py
│   ├── config.py            # Environment configuration via Pydantic
│   └── logging.py           # Structured logging setup
├── bot/
│   ├── __init__.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── commands.py      # /start, /help commands
│   │   ├── search.py        # Text queries (title + artist)
│   │   └── links.py         # Spotify & YouTube URLs
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── error_handler.py # Global exception handling middleware
│   └── ui/
│       ├── __init__.py
│       └── messages.py      # Formatted status and error messages
└── services/
    ├── __init__.py
    ├── audio/
    │   ├── __init__.py
    │   ├── extractor.py     # yt-dlp async subprocess execution
    │   ├── tagger.py        # mutagen ID3v2.4 and cover art embedding
    │   └── pipeline.py      # Audio processing orchestrator
    ├── metadata/
    │   ├── __init__.py
    │   ├── base.py          # MetadataResolver abstract base class
    │   ├── spotify.py       # Spotify URL resolver
    │   ├── youtube.py       # YouTube URL resolver
    │   └── search.py        # Query-to-track search resolver
    └── cache/
        ├── __init__.py
        └── repository.py    # SQLite cache for Telegram file_ids

tests/
├── conftest.py
├── unit/
│   ├── test_input_parser.py
│   ├── test_metadata_resolvers.py
│   └── test_tagger.py
├── contract/
│   └── test_bot_contracts.py
└── integration/
    └── test_audio_pipeline.py
```

**Structure Decision**: Selected standard single-project async Python architecture with clean layering: `bot` layer handles aiogram routing, `services` layer manages audio processing and caching, and `core` manages environment and logging.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| *None* | N/A | N/A |
