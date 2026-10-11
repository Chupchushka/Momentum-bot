# Tasks: Telegram Music Downloader

**Input**: Design documents from `/specs/001-telegram-music-downloader/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)
**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Exact file paths included in all task descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure (`src/bot/handlers`, `src/bot/middlewares`, `src/bot/ui`, `src/core`, `src/services/audio`, `src/services/metadata`, `src/services/cache`, `tests/unit`, `tests/contract`, `tests/integration`) per implementation plan
- [X] T002 Initialize project dependencies in `requirements.txt` with `aiogram>=3.13`, `yt-dlp`, `mutagen`, `aiohttp`, `pydantic-settings`, `pytest`, and `pytest-asyncio`
- [X] T003 [P] Configure environment settings schema in `src/core/config.py` with `TELEGRAM_BOT_TOKEN`, `TEMP_DIR` (default `/tmp/music_bot_tmp`), `MAX_FILE_SIZE_BYTES` (`52428800`), `MAX_DURATION_SECONDS` (`1200`), `SPOTIFY_CLIENT_ID`, and `SPOTIFY_CLIENT_SECRET`
- [X] T004 [P] Configure structured logging in `src/core/logging.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Implement base domain models in `src/services/metadata/base.py` for `UserRequest` (`raw_input` non-empty, max 500 characters, enum `request_type: TEXT_SEARCH, SPOTIFY_URL, YOUTUBE_URL, UNSUPPORTED`), `TrackMetadata` (`title` max 200 characters, `artist` max 200 characters, `duration_seconds <= 1200`), and `AudioDeliverable` (`format == 'mp3'`, `file_size_bytes <= 52428800`) per `data-model.md`
- [X] T006 [P] Implement SQLite cache repository in `src/services/cache/repository.py` for `CachedTrack` (`cache_key` format: `spotify:{id}`, `youtube:{id}`, or `search:{norm}`, `telegram_file_id` non-empty string, `hit_count >= 0`)
- [X] T007 [P] Implement global error handling middleware in `src/bot/middlewares/error_handler.py` catching unhandled exceptions and delivering user-friendly error messages
- [X] T008 [P] Implement UI status string constants and formatting helpers in `src/bot/ui/messages.py` per contract in `contracts/telegram-bot-interface.md`
- [X] T009 Implement core audio extractor subprocess wrapper in `src/services/audio/extractor.py` executing `yt-dlp` (`--extract-audio --audio-format mp3 --audio-quality 0 --no-playlist`) bounded by an `asyncio.Semaphore(4)` limit
- [X] T010 Implement aiogram Bot and Dispatcher entrypoint in `src/main.py` and register `/start` and `/help` command router in `src/bot/handlers/commands.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Download Song by Title and Artist Search (Priority: P1) 🎯 MVP

**Goal**: Allow users to send a text query (song title and artist) and receive a high-quality playable MP3 file.

**Independent Test**: Send message `Queen Bohemian Rhapsody` to the bot in Telegram. Verify receipt of a playable MP3 audio file with correct audio content.

### Tests for User Story 1

- [X] T011 [P] [US1] Unit test for query parsing and search resolver in `tests/unit/test_search_resolver.py`
- [X] T012 [P] [US1] Contract test for search text handler in `tests/contract/test_search_handler.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement text query search resolver in `src/services/metadata/search.py` using `ytsearch1:` query syntax to locate the top audio stream match and extract title/artist/duration metadata
- [X] T014 [US1] Implement basic audio delivery orchestrator in `src/services/audio/pipeline.py` connecting `SearchResolver`, `AudioExtractor`, and cache lookup
- [X] T015 [US1] Implement search message handler in `src/bot/handlers/search.py` handling plain text messages, executing `AudioService.process_request()`, and sending audio via `bot.send_audio(chat_id, audio=FSInputFile(file_path))`
- [X] T016 [US1] Implement temporary file cleanup context manager in `src/services/audio/pipeline.py` to guarantee unlinking of temporary MP3 files post-upload or on failure

**Checkpoint**: User Story 1 fully functional and testable independently (MVP ready!)

---

## Phase 4: User Story 2 - Download Song by Direct Link (Spotify or YouTube) (Priority: P1)

**Goal**: Allow users to paste a direct Spotify track URL or YouTube video URL and receive the corresponding MP3 file.

**Independent Test**: Send valid Spotify track URL (`https://open.spotify.com/track/...`) or YouTube URL (`https://www.youtube.com/watch?v=...`) to the bot. Verify receipt of matching MP3 audio file.

### Tests for User Story 2

- [ ] T017 [P] [US2] Unit tests for URL regex matching and parameter extraction in `tests/unit/test_link_resolvers.py`
- [ ] T018 [P] [US2] Contract test for direct link handler in `tests/contract/test_link_handler.py`

### Implementation for User Story 2

- [ ] T019 [US2] Implement YouTube URL resolver in `src/services/metadata/youtube.py` parsing `watch?v=`, `youtu.be/`, and `music.youtube.com/` URLs and rejecting playlists and live streams
- [ ] T020 [US2] Implement Spotify track resolver in `src/services/metadata/spotify.py` extracting track title, artist, album, and cover art, and mapping to the corresponding audio stream query
- [ ] T021 [US2] Implement direct link message handler in `src/bot/handlers/links.py` routing Spotify and YouTube URLs through `AudioService` and rejecting unsupported links

**Checkpoint**: User Stories 1 and 2 work independently.

---

## Phase 5: User Story 3 - Audio Quality and Metadata Enrichment (Priority: P2)

**Goal**: Embed comprehensive ID3 tags (title, artist, album, cover art) into the MP3 container and set Telegram audio player attributes.

**Independent Test**: Download a song via the bot and inspect it in the Telegram audio player and an audio tag inspector. Verify bitrate is up to 320 kbps, and title, artist, and cover art are displayed properly.

### Tests for User Story 3

- [X] T022 [P] [US3] Unit tests for ID3 tagging and cover art embedding in `tests/unit/test_tagger.py`

### Implementation for User Story 3

- [X] T023 [US3] Implement ID3 tagger in `src/services/audio/tagger.py` utilizing `mutagen.id3` to embed `TIT2` (title max 200 chars), `TPE1` (artist max 200 chars), `TALB` (album max 200 chars), and `APIC` (cover artwork downloaded via `aiohttp`)
- [X] T024 [US3] Integrate `AudioTagger` into `AudioPipeline` in `src/services/audio/pipeline.py` to tag converted MP3 files before dispatch
- [ ] T025 [US3] Update audio send call in `src/bot/handlers/search.py` and `src/bot/handlers/links.py` to populate native Telegram audio attributes: `title`, `performer`, `duration`, and `thumbnail=FSInputFile(cover_path)`

**Checkpoint**: All downloaded tracks feature rich metadata and native Telegram player artwork.

---

## Phase 6: User Story 4 - Progress Notification and Interactive Feedback (Priority: P3)

**Goal**: Provide real-time status updates ("Searching...", "Downloading audio...", "Uploading...") and handle boundary error cases gracefully.

**Independent Test**: Submit a download request; verify that status messages update at each lifecycle phase and are cleaned up after audio delivery, and verify oversized (>20 min or >50 MB) content produces helpful error messages.

### Tests for User Story 4

- [X] T026 [P] [US4] Unit test for progress status message lifecycle and error reporting in `tests/unit/test_ui_feedback.py`

### Implementation for User Story 4

- [X] T027 [US4] Implement async status message updater callback in `src/bot/ui/messages.py` updating Telegram message text between stages (`SEARCHING`, `DOWNLOADING`, `CONVERTING`, `SENDING`)
- [X] T028 [US4] Implement duration limit validation (`duration_seconds <= 1200`) and size limit validation (`file_size_bytes <= 52428800`) in `src/services/audio/pipeline.py` with friendly user rejection responses
- [X] T029 [US4] Integrate Telegram `file_id` caching in `src/bot/handlers/search.py` and `src/bot/handlers/links.py` to store and re-send cached audio instantly for repeat queries

**Checkpoint**: All user stories functional, fast-cached, and fully validated with boundary checks.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final configuration, end-to-end testing, and documentation

- [X] T030 [P] Create project configuration template in `.env.example` and setup guide in `README.md`
- [X] T031 [P] Integration test for complete audio pipeline in `tests/integration/test_audio_pipeline.py`
- [X] T032 Verify and execute quickstart validation suite per `specs/001-telegram-music-downloader/quickstart.md`
- [X] T033 Code cleanup, type annotation verification, and resource cleanup validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) - **BLOCKS** all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational phase completion.
  - US1 (P1): Direct search MVP.
  - US2 (P1): Direct links (independent of US1, shares audio pipeline).
  - US3 (P2): Metadata tagging (enhances deliverable from US1/US2).
  - US4 (P3): Progress feedback and caching (enhances UX and performance).
- **Polish (Phase 7)**: Depends on completion of all user story phases.

### User Story Dependencies

```
[Phase 1: Setup] ──► [Phase 2: Foundational]
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Phase 3: US1 Search]            [Phase 4: US2 Links]
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                [Phase 5: US3 Tagging & Quality]
                             │
                             ▼
                [Phase 6: US4 Progress & Caching]
                             │
                             ▼
                [Phase 7: Polish & Validation]
```

### Parallel Opportunities

- Within Phase 1: `T003` and `T004` can run in parallel.
- Within Phase 2: `T006`, `T007`, and `T008` can run in parallel.
- Within US1: Tests `T011` and `T012` can run in parallel.
- Within US2: Tests `T017` and `T018` can run in parallel.
- In US3/US4: Tests `T022` and `T026` can run in parallel.
- Across stories: Once Phase 2 completes, US1 and US2 can be developed in parallel by separate engineers.

---

## Parallel Example: User Story 1

```bash
# Launch tests for User Story 1 in parallel:
Task: "Unit test for query parsing and search resolver in tests/unit/test_search_resolver.py"
Task: "Contract test for search text handler in tests/contract/test_search_handler.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004).
2. Complete Phase 2: Foundational (T005–T010).
3. Complete Phase 3: User Story 1 (T011–T016).
4. **STOP and VALIDATE**: Test User Story 1 independently in Telegram with query `Bohemian Rhapsody Queen`.
5. Deploy/demo initial functional MVP.

### Incremental Delivery

1. Foundation ready (Setup + Foundational).
2. MVP delivered (User Story 1: Text search).
3. Direct Links added (User Story 2: Spotify & YouTube links).
4. Audio Quality & Cover Art enriched (User Story 3: ID3 tags & artwork).
5. Progress & Caching polished (User Story 4: Live progress & sub-second repeat responses).
