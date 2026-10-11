"""SQLite cache repository for Telegram file_id caching and instant delivery."""

import re
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("cache")


class CachedTrack(BaseModel):
    """Represents a cached audio deliverable indexed by source or query key."""

    cache_key: str = Field(min_length=1, description="Format: spotify:{id}, youtube:{id}, search:{norm}")
    telegram_file_id: str = Field(min_length=1, description="Telegram file_id for instantaneous resend")
    title: str = Field(min_length=1, description="Track title")
    artist: str = Field(min_length=1, description="Track artist")
    duration_seconds: int = Field(ge=1, description="Track duration in seconds")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hit_count: int = Field(default=0, ge=0, description="Usage counter")


class CacheRepository:
    """Manages SQLite persistent storage for cached Telegram file_ids."""

    def __init__(self, db_path: Optional[Path] = None):
        settings = get_settings()
        self.db_path = db_path or settings.cache_db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes SQLite schema if it does not exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_tracks (
                    cache_key TEXT PRIMARY KEY,
                    telegram_file_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cache_aliases (
                    alias TEXT PRIMARY KEY,
                    cache_key TEXT NOT NULL
                )"""
            )
            conn.commit()

    @staticmethod
    def normalize_query_key(query: str) -> str:
        """Normalizes free-form text search into search:{norm} key format."""
        cleaned = re.sub(r"[^\w\s]", "", query.lower()).strip()
        tokens = [token for token in cleaned.split() if token]
        normalized = "_".join(sorted(tokens))
        return f"search:{normalized}"

    def get(self, cache_key: str) -> Optional[CachedTrack]:
        """
        Retrieves a cached track by its key and increments the hit count.
        Returns None if key is not found.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM cached_tracks WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

            if not row:
                return None

            new_hits = row["hit_count"] + 1
            conn.execute(
                "UPDATE cached_tracks SET hit_count = ? WHERE cache_key = ?",
                (new_hits, cache_key),
            )
            conn.commit()

            return CachedTrack(
                cache_key=row["cache_key"],
                telegram_file_id=row["telegram_file_id"],
                title=row["title"],
                artist=row["artist"],
                duration_seconds=row["duration_seconds"],
                created_at=datetime.fromisoformat(row["created_at"]),
                hit_count=new_hits,
            )

    def put(self, track: CachedTrack) -> None:
        """Inserts or updates a cached track."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cached_tracks (
                    cache_key, telegram_file_id, title, artist, duration_seconds, created_at, hit_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    telegram_file_id=excluded.telegram_file_id,
                    title=excluded.title,
                    artist=excluded.artist,
                    duration_seconds=excluded.duration_seconds
                """,
                (
                    track.cache_key,
                    track.telegram_file_id,
                    track.title,
                    track.artist,
                    track.duration_seconds,
                    track.created_at.isoformat(),
                    track.hit_count,
                ),
            )
            conn.commit()
            logger.info("Cached track stored successfully with key: %s", track.cache_key)

    @staticmethod
    def query_alias(query: str) -> str:
        """Returns a compact stable token suitable for Telegram callback_data."""
        return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]

    def put_alias(self, alias: str, cache_key: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_aliases(alias, cache_key) VALUES (?, ?)",
                (alias, cache_key),
            )
            conn.commit()

    def get_alias(self, alias: str) -> Optional[str]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT cache_key FROM cache_aliases WHERE alias = ?", (alias,)
            ).fetchone()
            return row["cache_key"] if row else None
