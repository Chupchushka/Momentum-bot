"""Integration coverage for the audio pipeline with external services faked."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.audio.pipeline import AudioPipeline
from src.services.metadata.base import TrackMetadata


@pytest.mark.asyncio
async def test_audio_pipeline_processes_and_cleans_deliverable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = SimpleNamespace(
        max_duration_seconds=1200,
        max_file_size_bytes=52_428_800,
        ensure_temp_dir=lambda: tmp_path,
    )
    monkeypatch.setattr("src.services.audio.pipeline.get_settings", lambda: settings)

    metadata = TrackMetadata(
        track_id="yt:fixture",
        title="Fixture Song",
        artist="Fixture Artist",
        duration_seconds=210,
        source_url="https://youtube.example/watch?v=fixture",
    )
    resolver = MagicMock()
    resolver.can_handle.return_value = True
    resolver.resolve = AsyncMock(return_value=metadata)

    async def extract_audio(_source_url: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True)
        output_file = output_dir / "fixture.mp3"
        output_file.write_bytes(b"fixture audio")
        return output_file

    extractor = SimpleNamespace(extract_audio=AsyncMock(side_effect=extract_audio))
    async def tag_mp3(path: Path, _metadata: TrackMetadata) -> Path:
        assert path.read_bytes() == b"fixture audio"
        path.write_bytes(path.read_bytes() + b" tagged")
        path.with_name("cover.jpg").write_bytes(b"fixture image")
        return path.with_name("cover.jpg")

    tagger = SimpleNamespace(tag_mp3=AsyncMock(side_effect=tag_mp3))
    pipeline = AudioPipeline(
        extractor=extractor,
        cache_repo=MagicMock(),
        resolvers=[resolver],
        tagger=tagger,
    )
    stages = []

    async def record_stage(stage: str) -> None:
        stages.append(stage)

    deliverable, resolved_metadata = await pipeline.process_request(
        "Fixture Artist Fixture Song", status_callback=record_stage
    )

    assert resolved_metadata == metadata
    assert deliverable.file_path.read_bytes() == b"fixture audio tagged"
    assert deliverable.cover_path is not None
    assert deliverable.cover_path.name == "cover.jpg"
    assert deliverable.file_size_bytes == len(b"fixture audio tagged")
    assert stages == ["DOWNLOADING", "CONVERTING"]
    resolver.resolve.assert_awaited_once_with("Fixture Artist Fixture Song")
    extractor.extract_audio.assert_awaited_once_with(metadata.source_url, deliverable.file_path.parent)
    tagger.tag_mp3.assert_awaited_once_with(deliverable.file_path, metadata)

    pipeline.cleanup_deliverable(deliverable)
    assert not deliverable.file_path.exists()
    assert not deliverable.cover_path.exists()
    assert not deliverable.file_path.parent.exists()
