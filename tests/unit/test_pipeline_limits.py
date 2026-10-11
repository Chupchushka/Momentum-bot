"""Boundary validation tests for Phase 6 audio processing."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.audio.extractor import DurationLimitExceededError, FileSizeExceededError
from src.services.audio.pipeline import AudioPipeline


@pytest.mark.asyncio
async def test_pipeline_rejects_over_duration_metadata_before_extraction(monkeypatch, tmp_path: Path):
    settings = SimpleNamespace(
        max_duration_seconds=1200,
        max_file_size_bytes=52_428_800,
        ensure_temp_dir=lambda: tmp_path,
    )
    monkeypatch.setattr("src.services.audio.pipeline.get_settings", lambda: settings)
    extractor = SimpleNamespace(extract_audio=AsyncMock())
    pipeline = AudioPipeline(
        extractor=extractor,
        cache_repo=MagicMock(),
        tagger=MagicMock(),
    )
    pipeline.resolve_metadata = AsyncMock(return_value=SimpleNamespace(duration_seconds=1201))

    with pytest.raises(DurationLimitExceededError):
        await pipeline.process_request("track")

    extractor.extract_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_rejects_oversized_mp3_and_cleans_temp_files(monkeypatch, tmp_path: Path):
    settings = SimpleNamespace(
        max_duration_seconds=1200,
        max_file_size_bytes=3,
        ensure_temp_dir=lambda: tmp_path,
    )
    monkeypatch.setattr("src.services.audio.pipeline.get_settings", lambda: settings)
    mp3_path = tmp_path / "generated.mp3"

    async def extract_audio(_source_url, output_dir):
        output_dir.mkdir(parents=True)
        mp3_path_local = output_dir / "generated.mp3"
        mp3_path_local.write_bytes(b"oversized")
        return mp3_path_local

    metadata = SimpleNamespace(
        duration_seconds=180,
        source_url="https://example.test/audio",
    )
    pipeline = AudioPipeline(
        extractor=SimpleNamespace(extract_audio=extract_audio),
        cache_repo=MagicMock(),
        tagger=SimpleNamespace(tag_mp3=AsyncMock(return_value=None)),
    )
    pipeline.resolve_metadata = AsyncMock(return_value=metadata)

    with pytest.raises(FileSizeExceededError):
        await pipeline.process_request("track")

    assert list(tmp_path.iterdir()) == []
