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
                error_message TEXT
            )
        """)


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


# Initialize database on import
init_db()
