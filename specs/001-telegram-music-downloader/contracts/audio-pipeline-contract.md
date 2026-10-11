# Audio Pipeline Service Contract

**Feature**: [spec.md](../spec.md) | **Date**: 2026-10-11 | **Status**: Complete

## 1. Component Overview

The Audio Pipeline Service coordinates metadata resolution, audio extraction, transcoding, and ID3 tagging.

```
[aiogram Router]
       │
       ▼
[AudioService.process_request(query_or_url)]
       ├── 1. Cache Check -> CachedTrack?
       ├── 2. Resolver (SpotifyResolver or YouTubeResolver or SearchResolver) -> TrackMetadata
       ├── 3. Downloader (YtDlpAudioExtractor) -> Raw Audio Stream
       ├── 4. Transcoder & Tagger (FFmpeg + Mutagen) -> AudioDeliverable (.mp3)
       └── 5. Cleanup Context Manager -> File unlinked post-upload
```

---

## 2. Interface Definitions

### `AudioService` (Main Orchestrator)

```python
class AudioService:
    async def process_request(
        self,
        raw_input: str,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> AudioDeliverable:
        """
        Processes a raw input string (URL or text query), emits progress updates,
        and returns an AudioDeliverable containing the final MP3 file and metadata.
        """
        ...
```

### `MetadataResolver`

```python
class MetadataResolver(ABC):
    @abstractmethod
    def can_handle(self, raw_input: str) -> bool:
        """Determines if this resolver matches the input syntax."""
        ...

    @abstractmethod
    async def resolve(self, raw_input: str) -> TrackMetadata:
        """Extracts canonical metadata and best streaming source candidate."""
        ...
```

### `AudioExtractor`

```python
class AudioExtractor:
    async def extract_highest_quality(
        self,
        source_url: str,
        target_dir: Path
    ) -> Path:
        """
        Executes yt-dlp to download only the best audio stream
        without downloading video frames. Returns path to downloaded audio.
        """
        ...
```

### `AudioTagger`

```python
class AudioTagger:
    async def tag_mp3(
        self,
        mp3_path: Path,
        metadata: TrackMetadata,
        cover_image_bytes: Optional[bytes] = None
    ) -> None:
        """
        Applies ID3v2.4 tags (TIT2, TPE1, TALB, APIC) into the MP3 file in-place.
        """
        ...
```

---

## 3. Performance & Resource SLAs

- **Subprocess Timeout**: yt-dlp extraction process aborted if not completed within 60 seconds.
- **Max Concurrency**: Semaphore limit enforced across all active extractions (default: 4 concurrent processes).
- **Cleanup Guarantee**: `AudioDeliverable` implements an `async with` context manager or explicit cleanup hook ensuring temporary files are removed regardless of success or failure.
