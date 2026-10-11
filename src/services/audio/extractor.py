"""Asynchronous audio extractor wrapping yt-dlp with concurrency and timeout safeguards."""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project .venv/bin is in PATH for any subprocess invocations
project_root = Path(__file__).resolve().parent.parent.parent.parent
venv_bin = project_root / ".venv" / "bin"
if venv_bin.exists() and str(venv_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

py_bin = Path(sys.executable).parent
if str(py_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{py_bin}:{os.environ.get('PATH', '')}"

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("audio.extractor")


class AudioExtractionError(Exception):
    """Base exception for audio extraction failures."""
    pass


class TrackNotFoundError(AudioExtractionError):
    """Raised when query or URL yields no matching media."""
    pass


class DurationLimitExceededError(AudioExtractionError):
    """Raised when media exceeds allowable duration threshold."""
    pass


class FileSizeExceededError(AudioExtractionError):
    """Raised when an extracted MP3 exceeds Telegram's upload limit."""
    pass


class AudioExtractor:
    """Executes yt-dlp to extract high-quality audio streams asynchronously."""

    def __init__(self, semaphore_limit: Optional[int] = None):
        settings = get_settings()
        limit = semaphore_limit or settings.max_concurrent_downloads
        self._semaphore = asyncio.Semaphore(limit)
        self.timeout = settings.download_timeout_seconds
        self.max_duration = settings.max_duration_seconds

    @staticmethod
    def _get_ytdlp_cmd() -> List[str]:
        """
        Locates the best available yt-dlp executable across PATH, virtual environments, and python module.
        """
        # 1. Direct which search
        which_path = shutil.which("yt-dlp")
        if which_path:
            return [which_path]

        # 2. Next to running Python executable
        local_bin = Path(sys.executable).parent / "yt-dlp"
        if local_bin.exists() and os.access(local_bin, os.X_OK):
            return [str(local_bin)]

        # 3. Inside project .venv/bin
        venv_bin_path = Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "bin" / "yt-dlp"
        if venv_bin_path.exists() and os.access(venv_bin_path, os.X_OK):
            return [str(venv_bin_path)]

        # 4. Fallback: run via current Python module
        return [sys.executable, "-m", "yt_dlp"]

    async def search_candidates(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Fast search returning multiple candidate song entries without downloading media.
        """
        base_cmd = self._get_ytdlp_cmd()
        cmd = [
            *base_cmd,
            "--dump-json",
            "--no-playlist",
            "--no-warnings",
            "--flat-playlist",
            f"ytsearch{max_results}:{query}",
        ]

        logger.info("Searching candidates for: %s (limit: %d)", query, max_results)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
        except asyncio.TimeoutError:
            proc.kill()
            raise AudioExtractionError("Search query timed out")
        except FileNotFoundError:
            raise AudioExtractionError("yt-dlp binary is not installed or accessible in PATH")

        if proc.returncode != 0:
            err = stderr.decode(errors="ignore").strip()
            logger.warning("yt-dlp search candidates failed: %s", err)
            raise AudioExtractionError(f"Search failed: {err}")

        candidates: List[Dict[str, Any]] = []
        for line in stdout.decode(errors="ignore").splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            try:
                item = json.loads(line_str)
                if not item.get("id"):
                    continue
                if item.get("is_live"):
                    continue
                duration = item.get("duration") or 0
                if duration > self.max_duration or duration <= 0:
                    continue
                candidates.append(item)
            except json.JSONDecodeError:
                continue

        return candidates

    async def get_metadata_info(self, query_or_url: str) -> Dict[str, Any]:
        """
        Fetches media metadata using yt-dlp without downloading audio.
        """
        base_cmd = self._get_ytdlp_cmd()
        cmd = [
            *base_cmd,
            "--dump-json",
            "--no-playlist",
            "--no-warnings",
            "--default-search", "ytsearch1",
            query_or_url,
        ]

        logger.debug("Inspecting metadata: %s", " ".join(cmd))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            raise AudioExtractionError("Timed out fetching track metadata")
        except FileNotFoundError:
            raise AudioExtractionError("yt-dlp binary is not installed or accessible in PATH")

        if proc.returncode != 0:
            err = stderr.decode(errors="ignore").strip()
            logger.warning("yt-dlp metadata extraction failed: %s", err)
            if "not found" in err.lower() or "no video formats" in err.lower():
                raise TrackNotFoundError("Track could not be found")
            raise AudioExtractionError(f"Failed to inspect metadata: {err}")

        output_str = stdout.decode(errors="ignore").strip()
        if not output_str:
            raise TrackNotFoundError("Empty metadata returned by extractor")

        first_line = output_str.splitlines()[0]
        try:
            info = json.loads(first_line)
        except json.JSONDecodeError as exc:
            raise AudioExtractionError(f"Failed to parse yt-dlp JSON output: {exc}")

        duration = info.get("duration") or 0
        if duration > self.max_duration:
            raise DurationLimitExceededError(
                f"Track duration ({duration}s) exceeds maximum allowed limit ({self.max_duration}s)"
            )

        return info

    async def extract_audio(self, query_or_url: str, output_dir: Path) -> Path:
        """
        Extracts highest-quality audio stream to an MP3 file inside output_dir.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        template = str(output_dir / "%(id)s.%(ext)s")

        base_cmd = self._get_ytdlp_cmd()
        cmd = [
            *base_cmd,
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--format", "bestaudio[ext=m4a]/bestaudio/best",
            "--no-playlist",
            "--no-warnings",
            "--no-check-certificates",
            "--default-search", "ytsearch1",
            "--output", template,
            "--print", "after_move:filepath",
            query_or_url,
        ]

        logger.info("Extracting audio for: %s", query_or_url)
        async with self._semaphore:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                raise AudioExtractionError(f"Audio extraction timed out after {self.timeout}s")
            except FileNotFoundError:
                raise AudioExtractionError("yt-dlp binary is not installed or accessible in PATH")

            if proc.returncode != 0:
                err = stderr.decode(errors="ignore").strip()
                logger.error("Audio extraction failed with code %d: %s", proc.returncode, err)
                if "not found" in err.lower() or "video unavailable" in err.lower():
                    raise TrackNotFoundError(f"Media not available: {err}")
                raise AudioExtractionError(f"Extraction failed: {err}")

            lines = [line.strip() for line in stdout.decode(errors="ignore").splitlines() if line.strip()]
            if not lines:
                raise AudioExtractionError("yt-dlp completed but did not return output file path")

            output_file = Path(lines[-1])
            if not output_file.exists():
                mp3s = list(output_dir.glob("*.mp3"))
                if mp3s:
                    output_file = mp3s[0]
                else:
                    raise AudioExtractionError(f"Extracted audio file not found at {output_file}")

            logger.info("Successfully extracted audio to: %s", output_file)
            return output_file
