"""ID3 metadata tagging and cover artwork embedding for MP3 audio deliverables."""

import asyncio
from pathlib import Path
from typing import Optional

import aiohttp
from mutagen.id3 import ID3, APIC, TALB, TIT2, TPE1, ID3NoHeaderError

from src.core.logging import get_logger
from src.services.metadata.base import TrackMetadata

logger = get_logger("audio.tagger")


class AudioTagger:
    """Embeds ID3v2.4 tags and album artwork into MP3 containers."""

    def __init__(self, request_timeout_seconds: float = 15.0):
        self.request_timeout_seconds = request_timeout_seconds

    @staticmethod
    def _detect_mime_type(data: bytes) -> str:
        """Infers MIME type from magic bytes in raw image payload."""
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data[:4] == b"RIFF" and b"WEBP" in data[8:12]:
            return "image/webp"
        return "image/jpeg"

    async def fetch_cover_image(self, url: str) -> Optional[bytes]:
        """
        Downloads remote cover artwork asynchronously via aiohttp.
        Returns image bytes or None if retrieval fails.
        """
        if not url:
            return None

        timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        logger.debug("Fetched cover image (%d bytes) from %s", len(data), url)
                        return data
                    logger.warning("Failed to download cover art from %s: HTTP %d", url, response.status)
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Network error fetching cover artwork from %s: %s", url, exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected error downloading cover artwork from %s: %s", url, exc)
            return None

    async def tag_mp3(
        self,
        mp3_path: Path,
        metadata: TrackMetadata,
        cover_image_bytes: Optional[bytes] = None,
        save_cover_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Applies ID3v2.4 tags (TIT2, TPE1, TALB, APIC) into the MP3 file in-place.
        Saves cover thumbnail to disk if available and returns its Path.
        """
        if not mp3_path.exists():
            raise FileNotFoundError(f"Cannot tag non-existent MP3 file: {mp3_path}")

        try:
            tags = ID3(str(mp3_path))
        except ID3NoHeaderError:
            tags = ID3()

        # Enforce max 200 character bounds on ID3 text tags
        title = (metadata.title or "")[:200].strip()
        artist = (metadata.artist or "")[:200].strip()
        album = (metadata.album or "")[:200].strip() if metadata.album else None

        if title:
            tags.add(TIT2(encoding=3, text=[title]))
        if artist:
            tags.add(TPE1(encoding=3, text=[artist]))
        if album:
            tags.add(TALB(encoding=3, text=[album]))
        else:
            tags.delall("TALB")

        # Resolve cover image bytes
        if cover_image_bytes is None and metadata.cover_art_url:
            cover_image_bytes = await self.fetch_cover_image(metadata.cover_art_url)

        cover_path: Optional[Path] = None
        if cover_image_bytes:
            mime = self._detect_mime_type(cover_image_bytes)
            tags.delall("APIC")
            tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=cover_image_bytes,
                )
            )

            # Persist cover artwork to disk for Telegram thumbnail usage
            ext = ".png" if mime == "image/png" else ".jpg"
            target_cover_path = save_cover_path or (mp3_path.parent / f"cover{ext}")
            try:
                target_cover_path.write_bytes(cover_image_bytes)
                cover_path = target_cover_path
                logger.debug("Saved thumbnail image to %s", cover_path)
            except Exception as exc:
                logger.warning("Could not persist thumbnail to %s: %s", target_cover_path, exc)

        # Save ID3 tags to MP3 container (v2.4 per requirements)
        tags.save(str(mp3_path), v2_version=4)
        logger.info(
            "Successfully tagged %s with '%s - %s' (Cover embedded: %s)",
            mp3_path.name,
            artist,
            title,
            cover_path is not None,
        )

        return cover_path
