# 🎵 Telegram Music Downloader

A Telegram bot that finds a track, delivers it as an MP3, and remembers uploaded files so repeat requests can be sent quickly.

## What it can do

- Search by song title or artist and choose from matching tracks.
- Process individual YouTube video links.
- Process individual Spotify track links with [spotDL](https://github.com/spotdl/spotify-downloader), which finds a matching recording on YouTube.
- Add track metadata and available cover art to the MP3.
- Cache Telegram file IDs in SQLite for faster repeat delivery.
- Reject tracks over 20 minutes or 50 MB.

Playlists and albums are not supported. Spotify links provide track details; audio is matched and sourced from YouTube.

## Deploy with Docker

Docker Compose is the easiest way to run the bot. You need Docker with the Compose plugin and a Telegram bot token from [@BotFather](https://t.me/BotFather).

```bash
cp .env.example .env
```

Open `.env`, set `TELEGRAM_BOT_TOKEN`, then build and start the bot:

```bash
docker compose up --build -d
```

Useful commands:

```bash
docker compose logs -f bot  # Follow logs
docker compose restart bot  # Restart after configuration changes
docker compose down         # Stop the bot
```

Compose stores the SQLite cache in a persistent Docker volume. The image includes FFmpeg and runs the bot as an unprivileged user.

## Run locally

Requires Python 3.11 or newer and internet access.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `TELEGRAM_BOT_TOKEN` in `.env`, then start the polling bot:

```bash
python -m src.main
```

The `static-ffmpeg` package provides FFmpeg for local audio processing. If it does not provide a binary for your platform, install FFmpeg separately and ensure `ffmpeg` is on your `PATH`.

## Configuration

All settings can be set in `.env` or as environment variables.

| Variable | Default | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — | Required token from @BotFather. |
| `MAX_DURATION_SECONDS` | `1200` | Maximum track length (20 minutes). |
| `MAX_FILE_SIZE_BYTES` | `52428800` | Maximum MP3 size (50 MiB). |
| `MAX_CONCURRENT_DOWNLOADS` | `4` | Maximum concurrent audio extraction jobs. |
| `DOWNLOAD_TIMEOUT_SECONDS` | `60` | Download and conversion timeout. |
| `CACHE_DB_PATH` | `cache.db` | SQLite cache location. Docker sets this to `/data/cache.db`. |
| `TEMP_DIR` | `/tmp/music_bot_tmp` | Working directory for temporary audio files. |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |

## Troubleshooting

- **`No module named spotdl`**: Install dependencies in the same Python environment that runs the bot with `python -m pip install -r requirements.txt`, then restart it. For Docker, rebuild with `docker compose up --build -d`.
- **FFmpeg errors**: Confirm FFmpeg is available. The Docker image installs it automatically; local installations may need a separate FFmpeg install.
- **Missing token**: Confirm `.env` contains a non-empty `TELEGRAM_BOT_TOKEN`. When using Compose, recreate the container after changing `.env`.
- **Track could not be processed**: Check that the link is a single track or video, the content is accessible, and it meets the duration and file-size limits.

## Tests

Run the unit and contract suites:

```bash
pytest tests/unit tests/contract -v
```

Run integration tests that do not require live external media services:

```bash
pytest tests/integration -v -m "not e2e"
```

Manual Telegram scenarios are documented in [`specs/001-telegram-music-downloader/quickstart.md`](specs/001-telegram-music-downloader/quickstart.md).
