"""Search resolver resolving text queries to single or multiple track metadata candidates."""

import re
from typing import List, Optional

from src.core.logging import get_logger
from src.services.audio.extractor import AudioExtractor, TrackNotFoundError
from src.services.metadata.base import MetadataResolver, TrackMetadata

logger = get_logger("metadata.search")


class SearchResolver(MetadataResolver):
    """Resolves natural language queries (artist + song title) via YouTube audio search."""

    def __init__(self, extractor: Optional[AudioExtractor] = None):
        self.extractor = extractor or AudioExtractor()

    def can_handle(self, raw_input: str) -> bool:
        """Determines if the input is a valid non-command, non-URL search query."""
        cleaned = raw_input.strip()
        if not cleaned:
            return False
        if cleaned.startswith("/"):
            return False
        if re.match(r"^(https?://|www\.|spotify:)", cleaned, re.IGNORECASE):
            return False
        return True

    @staticmethod
    def _clean_track_title(raw_title: str) -> str:
        """Removes common promotional, resolution, and video tags from title strings."""
        patterns = [
            r"\(Official (?:Video|Music Video|Audio|HD Video|Lyric Video|Remastered)\)",
            r"\[Official (?:Video|Music Video|Audio|HD Video|Lyric Video|Remastered)\]",
            r"\(Lyrics?\)",
            r"\[Lyrics?\]",
            r"\(Audio\)",
            r"\[Audio\]",
            r"\(HD\)",
            r"\[HD\]",
            r"\(HQ\)",
            r"\[HQ\]",
            r"\(4K(?: - 60 FPS)?\)",
            r"\[4K(?: - 60 FPS)?\]",
        ]
        cleaned = raw_title
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _parse_candidate_metadata(self, info: dict, fallback_query: str) -> TrackMetadata:
        """Extracts and normalizes title, artist, and duration from yt-dlp entry info."""
        track_id = info.get("id")
        raw_title = info.get("title") or fallback_query

        # Check for explicit artist/track fields
        track_title = info.get("track")
        track_artist = info.get("artist") or info.get("creator") or info.get("uploader")

        if not track_title:
            cleaned_title = self._clean_track_title(raw_title)
            if " - " in cleaned_title:
                parts = cleaned_title.split(" - ", 1)
                track_artist = parts[0].strip()
                track_title = parts[1].strip()
            elif " – " in cleaned_title:  # en-dash
                parts = cleaned_title.split(" – ", 1)
                track_artist = parts[0].strip()
                track_title = parts[1].strip()
            else:
                track_title = cleaned_title
                if not track_artist:
                    track_artist = "Unknown Artist"

        track_title = (track_title or "Unknown Track")[:200].strip()
        track_artist = (track_artist or "Unknown Artist")[:200].strip()
        duration = int(info.get("duration") or 0)
        source_url = info.get("webpage_url") or f"https://www.youtube.com/watch?v={track_id}"
        thumbnail = info.get("thumbnail")

        return TrackMetadata(
            track_id=f"yt:{track_id}",
            title=track_title,
            artist=track_artist,
            duration_seconds=max(1, duration),
            cover_art_url=thumbnail,
            source_url=source_url,
        )

    async def search_candidates(self, query: str, limit: int = 5) -> List[TrackMetadata]:
        """
        Searches for multiple candidate tracks matching the query.
        """
        cleaned_query = query.strip()
        logger.info("Searching candidates for query: '%s'", cleaned_query)
        raw_candidates = await self.extractor.search_candidates(cleaned_query, max_results=limit)

        results: List[TrackMetadata] = []
        for item in raw_candidates:
            metadata = self._parse_candidate_metadata(item, cleaned_query)
            results.append(metadata)

        return results

    async def resolve(self, raw_input: str) -> TrackMetadata:
        """Resolves natural language query to the single best matching candidate."""
        candidates = await self.search_candidates(raw_input, limit=1)
        if not candidates:
            # Fallback to single info query if flat-playlist search returned empty
            info = await self.extractor.get_metadata_info(f"ytsearch1:{raw_input.strip()}")
            return self._parse_candidate_metadata(info, raw_input.strip())
        return candidates[0]
