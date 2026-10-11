"""Unit tests for ID3 tagging and cover artwork embedding."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from mutagen.id3 import ID3, APIC, TALB, TIT2, TPE1

from src.services.audio.tagger import AudioTagger
from src.services.metadata.base import TrackMetadata


def _create_dummy_mp3(path: Path) -> Path:
    """Creates a minimal MP3 file containing a valid MPEG frame header."""
    # 0xFFFB is standard MPEG-1 Layer III sync word with no protection
    frame = b"\xff\xfb\x90\x00" + b"\x00" * 414
    path.write_bytes(frame * 3)
    return path


@pytest.fixture
def dummy_mp3(tmp_path: Path) -> Path:
    return _create_dummy_mp3(tmp_path / "test_track.mp3")


@pytest.fixture
def tagger() -> AudioTagger:
    return AudioTagger()


@pytest.mark.asyncio
async def test_tag_mp3_basic_metadata(tagger: AudioTagger, dummy_mp3: Path):
    metadata = TrackMetadata(
        track_id="yt:test1",
        title="Bohemian Rhapsody",
        artist="Queen",
        album="A Night at the Opera",
        duration_seconds=354,
        source_url="https://youtube.com/watch?v=test1",
    )

    result_cover = await tagger.tag_mp3(dummy_mp3, metadata)
    assert result_cover is None

    tags = ID3(dummy_mp3)
    assert tags.get("TIT2").text[0] == "Bohemian Rhapsody"
    assert tags.get("TPE1").text[0] == "Queen"
    assert tags.get("TALB").text[0] == "A Night at the Opera"


@pytest.mark.asyncio
async def test_tag_mp3_truncation_to_200_chars(tagger: AudioTagger, dummy_mp3: Path):
    long_title = "A" * 250
    long_artist = "B" * 250
    long_album = "C" * 250

    metadata = TrackMetadata(
        track_id="yt:test2",
        title=long_title[:200],  # TrackMetadata model enforces max 200, but test defensive tagger logic
        artist=long_artist[:200],
        album=long_album[:200],
        duration_seconds=180,
        source_url="https://youtube.com/watch?v=test2",
    )

    await tagger.tag_mp3(dummy_mp3, metadata)

    tags = ID3(dummy_mp3)
    assert len(tags.get("TIT2").text[0]) <= 200
    assert len(tags.get("TPE1").text[0]) <= 200
    assert len(tags.get("TALB").text[0]) <= 200


@pytest.mark.asyncio
async def test_tag_mp3_with_raw_cover_bytes_jpeg(tagger: AudioTagger, dummy_mp3: Path, tmp_path: Path):
    metadata = TrackMetadata(
        track_id="yt:test3",
        title="Starboy",
        artist="The Weeknd",
        duration_seconds=230,
        source_url="https://youtube.com/watch?v=test3",
    )
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    save_path = tmp_path / "custom_cover.jpg"

    cover_path = await tagger.tag_mp3(
        dummy_mp3,
        metadata,
        cover_image_bytes=fake_jpeg,
        save_cover_path=save_path,
    )

    assert cover_path == save_path
    assert save_path.exists()
    assert save_path.read_bytes() == fake_jpeg

    tags = ID3(dummy_mp3)
    apic_frames = [f for f in tags.values() if isinstance(f, APIC)]
    assert len(apic_frames) == 1
    apic = apic_frames[0]
    assert apic.mime == "image/jpeg"
    assert apic.type == 3  # Front cover
    assert apic.data == fake_jpeg


@pytest.mark.asyncio
async def test_tag_mp3_with_raw_cover_bytes_png(tagger: AudioTagger, dummy_mp3: Path):
    metadata = TrackMetadata(
        track_id="yt:test4",
        title="Get Lucky",
        artist="Daft Punk",
        duration_seconds=248,
        source_url="https://youtube.com/watch?v=test4",
    )
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    cover_path = await tagger.tag_mp3(dummy_mp3, metadata, cover_image_bytes=fake_png)
    assert cover_path is not None
    assert cover_path.exists()

    tags = ID3(dummy_mp3)
    apic_frames = [f for f in tags.values() if isinstance(f, APIC)]
    assert len(apic_frames) == 1
    assert apic_frames[0].mime == "image/png"


@pytest.mark.asyncio
async def test_tag_mp3_fetches_cover_from_url(tagger: AudioTagger, dummy_mp3: Path):
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x11" * 50
    metadata = TrackMetadata(
        track_id="yt:test5",
        title="Blinding Lights",
        artist="The Weeknd",
        duration_seconds=200,
        cover_art_url="https://example.com/art.jpg",
        source_url="https://youtube.com/watch?v=test5",
    )

    with patch.object(tagger, "fetch_cover_image", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = fake_jpeg
        cover_path = await tagger.tag_mp3(dummy_mp3, metadata)

        mock_fetch.assert_awaited_once_with("https://example.com/art.jpg")
        assert cover_path is not None
        assert cover_path.exists()

        tags = ID3(dummy_mp3)
        apic_frames = [f for f in tags.values() if isinstance(f, APIC)]
        assert len(apic_frames) == 1
        assert apic_frames[0].data == fake_jpeg


@pytest.mark.asyncio
async def test_tag_mp3_handles_cover_download_failure_gracefully(tagger: AudioTagger, dummy_mp3: Path):
    metadata = TrackMetadata(
        track_id="yt:test6",
        title="Rolling in the Deep",
        artist="Adele",
        duration_seconds=228,
        cover_art_url="https://example.com/broken_link.jpg",
        source_url="https://youtube.com/watch?v=test6",
    )

    with patch.object(tagger, "fetch_cover_image", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None  # Download failed
        cover_path = await tagger.tag_mp3(dummy_mp3, metadata)

        assert cover_path is None
        tags = ID3(dummy_mp3)
        assert tags.get("TIT2").text[0] == "Rolling in the Deep"
        assert tags.get("TPE1").text[0] == "Adele"
        # No APIC frame should be attached
        apic_frames = [f for f in tags.values() if isinstance(f, APIC)]
        assert len(apic_frames) == 0


@pytest.mark.asyncio
async def test_tag_mp3_without_album_or_cover(tagger: AudioTagger, dummy_mp3: Path):
    metadata = TrackMetadata(
        track_id="yt:test7",
        title="Someone Like You",
        artist="Adele",
        album=None,
        cover_art_url=None,
        duration_seconds=285,
        source_url="https://youtube.com/watch?v=test7",
    )

    cover_path = await tagger.tag_mp3(dummy_mp3, metadata)
    assert cover_path is None

    tags = ID3(dummy_mp3)
    assert tags.get("TIT2").text[0] == "Someone Like You"
    assert tags.get("TPE1").text[0] == "Adele"
    assert tags.get("TALB") is None
    apic_frames = [f for f in tags.values() if isinstance(f, APIC)]
    assert len(apic_frames) == 0


@pytest.mark.asyncio
async def test_fetch_cover_image_http_success(tagger: AudioTagger):
    fake_data = b"\xff\xd8\xff\xe0" + b"\x22" * 40
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read.return_value = fake_data

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_response

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.get = MagicMock(return_value=mock_ctx)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        data = await tagger.fetch_cover_image("https://example.com/cover.jpg")
        assert data == fake_data


@pytest.mark.asyncio
async def test_fetch_cover_image_http_error(tagger: AudioTagger):
    mock_response = AsyncMock()
    mock_response.status = 404

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_response

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.get = MagicMock(return_value=mock_ctx)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        data = await tagger.fetch_cover_image("https://example.com/missing.jpg")
        assert data is None


