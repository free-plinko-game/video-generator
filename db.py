"""Database operations for the Liminal Space Video Generator."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

import config


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database with the required schema."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                location TEXT,
                time_of_day TEXT,
                mood TEXT,
                detail TEXT,
                memory_hook TEXT,
                image_prompt TEXT,
                voiceover_script TEXT,
                screen_text TEXT,
                image_path TEXT,
                voice_path TEXT,
                music_path TEXT,
                output_path TEXT,
                duration_seconds REAL,
                error_message TEXT,
                youtube_id TEXT,
                youtube_url TEXT,
                youtube_status TEXT,
                youtube_published_at TIMESTAMP,
                youtube_title TEXT,
                youtube_description TEXT
            )
        """)

    # Run migrations for existing databases
    _migrate_db()


def _migrate_db():
    """Add new columns to existing databases."""
    youtube_columns = [
        ("youtube_id", "TEXT"),
        ("youtube_url", "TEXT"),
        ("youtube_status", "TEXT"),
        ("youtube_published_at", "TIMESTAMP"),
        ("youtube_title", "TEXT"),
        ("youtube_description", "TEXT"),
    ]

    with get_db() as conn:
        # Get existing columns
        cursor = conn.execute("PRAGMA table_info(videos)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Add missing columns
        for col_name, col_type in youtube_columns:
            if col_name not in existing_columns:
                conn.execute(f"ALTER TABLE videos ADD COLUMN {col_name} {col_type}")


def create_video() -> int:
    """Create a new video record and return its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO videos (status) VALUES ('pending')"
        )
        return cursor.lastrowid


def update_video(video_id: int, **kwargs) -> None:
    """Update video record with given fields."""
    if not kwargs:
        return

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [video_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE videos SET {fields} WHERE id = ?",
            values
        )


def update_status(video_id: int, status: str) -> None:
    """Update the status of a video."""
    update_video(video_id, status=status)


def set_error(video_id: int, error_message: str) -> None:
    """Set an error message and mark video as failed."""
    update_video(video_id, status='failed', error_message=error_message)


def mark_complete(video_id: int, output_path: str, duration_seconds: float) -> None:
    """Mark video as complete with output path and duration."""
    update_video(
        video_id,
        status='complete',
        completed_at=datetime.now().isoformat(),
        output_path=output_path,
        duration_seconds=duration_seconds
    )


def get_video(video_id: int) -> Optional[Dict[str, Any]]:
    """Get a video by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM videos WHERE id = ?",
            (video_id,)
        ).fetchone()
        return dict(row) if row else None


def get_recent_videos(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent videos ordered by creation date."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM videos ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_all_videos() -> List[Dict[str, Any]]:
    """Get all videos ordered by creation date."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM videos ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_completed_videos() -> List[Dict[str, Any]]:
    """Get all completed videos."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM videos WHERE status = 'complete' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


# YouTube-specific functions

def update_youtube_status(video_id: int, status: str) -> None:
    """Update the YouTube upload status of a video."""
    update_video(video_id, youtube_status=status)


def set_youtube_published(video_id: int, youtube_id: str, youtube_url: str,
                          title: str, description: str) -> None:
    """Mark video as published to YouTube."""
    update_video(
        video_id,
        youtube_id=youtube_id,
        youtube_url=youtube_url,
        youtube_status='published',
        youtube_published_at=datetime.now().isoformat(),
        youtube_title=title,
        youtube_description=description
    )


def set_youtube_failed(video_id: int) -> None:
    """Mark YouTube upload as failed."""
    update_video(video_id, youtube_status='failed')


def get_unpublished_videos() -> List[Dict[str, Any]]:
    """Get completed videos that haven't been published to YouTube."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM videos
               WHERE status = 'complete'
               AND (youtube_status IS NULL OR youtube_status = 'failed')
               ORDER BY created_at DESC"""
        ).fetchall()
        return [dict(row) for row in rows]


def get_published_videos() -> List[Dict[str, Any]]:
    """Get videos that have been published to YouTube."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM videos
               WHERE youtube_status = 'published'
               ORDER BY youtube_published_at DESC"""
        ).fetchall()
        return [dict(row) for row in rows]


# Initialize database on import
init_db()
