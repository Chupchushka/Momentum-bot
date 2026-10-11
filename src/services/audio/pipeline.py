"""Audio delivery orchestrator connecting metadata resolvers, audio extraction, and cleanup."""

import asyncio
import re
import shutil
import sys
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable, List, Optional, Tuple
from uuid import uuid4

from mutagen.id3 import ID3
from mutagen.mp3 import MP3

from src.core.config import get_settings
from src.core.logging import get_logger
from src.services.audio.extractor import (
    AudioExtractor,
    AudioExtractionError,
    DurationLimitExceededError,
    FileSizeExceededError,
)
from src.services.audio.tagger import AudioTagger
from src.services.cache.repository import CacheRepository, CachedTrack
from src.services.metadata.base import AudioDeliverable, MetadataResolver, TrackMetadata
from src.services.metadata.search import SearchResolver

logger = get_logger("audio.pipeline")


class AudioPipeline:
    """Orchestrates resolution, extraction, caching, and cleanup of audio requests."""

    def __init__(
        self,
        extractor: Optional[AudioExtractor] = None,
        cache_repo: Optional[CacheRepository] = None,
        resolvers: Optional[List[MetadataResolver]] = None,
        tagger: Optional[AudioTagger] = None,
    ):
        self.settings = get_settings()
        self.extractor = extractor or AudioExtractor()
        self.cache_repo = cache_repo or CacheRepository()
        self.tagger = tagger or AudioTagger()
        self.search_resolver = SearchResolver(self.extractor)
        self.resolvers = resolvers or [self.search_resolver]

    def register_resolver(self, resolver: MetadataResolver) -> None:
        """Prepends a resolver to allow specialized URL handlers before fallback search."""
        self.resolvers.insert(0, resolver)

    async def search_candidates(self, query: str, limit: int = 5) -> List[TrackMetadata]:
        """Returns multiple candidate matches for an interactive user menu."""
        return await self.search_resolver.search_candidates(query, limit=limit)

    async def resolve_metadata(self, raw_input: str) -> TrackMetadata:
        """Finds matching resolver or resolves YouTube URL directly."""
        cleaned = raw_input.strip()

        # Direct YouTube video URL resolution
        if "youtube.com/watch" in cleaned or "youtu.be/" in cleaned or "music.youtube.com/watch" in cleaned:
            info = await self.extractor.get_metadata_info(cleaned)
            return self.search_resolver._parse_candidate_metadata(info, cleaned)

        for resolver in self.resolvers:
            if resolver.can_handle(cleaned):
                return await resolver.resolve(cleaned)

        raise AudioExtractionError("Unsupported input or no resolver available")

    async def process_request(
        self,
        raw_input: str,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Tuple[AudioDeliverable, TrackMetadata]:
        """
        Processes a search or URL request, downloads the audio, and returns
        the generated AudioDeliverable along with TrackMetadata.
        """
        # spotDL resolves a Spotify track to a matching YouTube recording and
        # downloads it with Spotify metadata/artwork attached.
        cleaned = raw_input.strip()
        spotify_match = re.search(
            r"open\.spotify\.com/track/([A-Za-z0-9]+)", cleaned, re.IGNORECASE
        )

        if spotify_match:
            return await self._process_spotify_link(cleaned, spotify_match.group(1), status_callback)

        # 1. Resolve canonical metadata
        metadata = await self.resolve_metadata(raw_input)
        if metadata.duration_seconds > self.settings.max_duration_seconds:
            raise DurationLimitExceededError(
                f"Track duration exceeds maximum allowed limit ({self.settings.max_duration_seconds}s)"
            )

        # 2. Prepare temporary directory for extraction
        task_id = str(uuid4())
        task_temp_dir = self.settings.ensure_temp_dir() / task_id

        try:
            if status_callback:
                await status_callback("DOWNLOADING")

            # 3. Extract audio
            mp3_path = await self.extractor.extract_audio(metadata.source_url, task_temp_dir)

            # 4. Embed ID3 metadata and persist artwork for Telegram thumbnails.
            if status_callback:
                await status_callback("CONVERTING")
            cover_path = await self.tagger.tag_mp3(
                mp3_path,
                metadata,
            )

            # 5. Validate file size (Telegram 50MB limit)
            file_size = mp3_path.stat().st_size
            if file_size > self.settings.max_file_size_bytes:
                raise FileSizeExceededError(
                    f"Generated file ({file_size} bytes) exceeds limit ({self.settings.max_file_size_bytes} bytes)"
                )

            deliverable = AudioDeliverable(
                file_path=mp3_path,
                cover_path=cover_path,
                file_size_bytes=file_size,
                bitrate_kbps=320,
                duration_seconds=metadata.duration_seconds,
                format="mp3",
            )
            return deliverable, metadata

        except Exception:
            # Clean up directory on error
            if task_temp_dir.exists():
                shutil.rmtree(task_temp_dir, ignore_errors=True)
            raise

    async def _process_spotify_link(self, raw_input, track_id, status_callback):
        """Download one Spotify track through spotDL and normalize its ID3 data."""
        task_temp_dir = self.settings.ensure_temp_dir() / str(uuid4())
        task_temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            if status_callback:
                await status_callback("DOWNLOADING")
            cmd = [
                sys.executable, "-m", "spotdl", "download", raw_input,
                "--format", "mp3", "--output", str(task_temp_dir / "{title}.{output-ext}"),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.settings.download_timeout_seconds,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise AudioExtractionError("Spotify download timed out")
            if proc.returncode:
                logger.warning("spotDL failed: %s", stderr.decode(errors="ignore")[-1000:])
                raise AudioExtractionError("spotDL could not download the Spotify track")

            files = list(task_temp_dir.glob("*.mp3"))
            if not files:
                raise TrackNotFoundError("spotDL produced no MP3 output")
            mp3_path = files[0]
            tags = ID3(str(mp3_path))
            title = str(tags.get("TIT2").text[0] if tags.get("TIT2") else "Unknown Track")[:200]
            artist = str(tags.get("TPE1").text[0] if tags.get("TPE1") else "Unknown Artist")[:200]
            album = str(tags.get("TALB").text[0] if tags.get("TALB") else "")[:200] or None
            duration = max(1, int(MP3(str(mp3_path)).info.length))
            if duration > self.settings.max_duration_seconds:
                raise DurationLimitExceededError("Track exceeds maximum duration")
            size = mp3_path.stat().st_size
            if size > self.settings.max_file_size_bytes:
                raise FileSizeExceededError("Track exceeds maximum file size")
            metadata = TrackMetadata(
                track_id=f"spotify:{track_id}", title=title, artist=artist, album=album,
                duration_seconds=duration, source_url=raw_input,
            )
            if status_callback:
                await status_callback("CONVERTING")
            cover_path = None
            for frame in tags.getall("APIC"):
                suffix = ".png" if frame.mime == "image/png" else ".jpg"
                cover_path = task_temp_dir / f"cover{suffix}"
                cover_path.write_bytes(frame.data)
                break
            return AudioDeliverable(
                file_path=mp3_path, cover_path=cover_path, file_size_bytes=size,
                bitrate_kbps=320, duration_seconds=duration, format="mp3",
            ), metadata
        except Exception:
            shutil.rmtree(task_temp_dir, ignore_errors=True)
            raise

    @staticmethod
    def cleanup_deliverable(deliverable: AudioDeliverable) -> None:
        """
        Safely removes the temporary deliverable file and its parent task directory.
        """
        try:
            if deliverable.file_path.exists():
                parent_dir = deliverable.file_path.parent
                deliverable.file_path.unlink(missing_ok=True)
                if deliverable.cover_path and deliverable.cover_path.exists():
                    deliverable.cover_path.unlink(missing_ok=True)
                if parent_dir.exists() and parent_dir.is_dir():
                    shutil.rmtree(parent_dir, ignore_errors=True)
                logger.debug("Cleaned up temporary audio files at %s", deliverable.file_path)
        except Exception as exc:
            logger.warning("Failed to clean up deliverable %s: %s", deliverable.file_path, exc)


_pipeline_instance: Optional[AudioPipeline] = None


def get_audio_pipeline() -> AudioPipeline:
    """Returns singleton AudioPipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = AudioPipeline()
    return _pipeline_instance
