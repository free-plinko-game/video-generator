"""Database operations for the Content Factory."""

import json
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

import config


def get_connection():
    """Get a database connection."""
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
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
        # Users table for authentication
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP
            )
        """)

        # YouTube accounts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS youtube_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                channel_id TEXT,
                channel_name TEXT,
                credentials_path TEXT NOT NULL,
                is_default BOOLEAN DEFAULT 0,
                videos_published INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP
            )
        """)

        # Video formats table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS video_formats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT,
                min_duration INTEGER,
                max_duration INTEGER,
                target_duration INTEGER,
                scene_count_min INTEGER,
                scene_count_max INTEGER,
                scene_count_default INTEGER,
                script_style TEXT,
                needs_intro BOOLEAN DEFAULT 0,
                needs_outro BOOLEAN DEFAULT 0,
                transition_style TEXT,
                aspect_ratio TEXT DEFAULT '9:16',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Content types table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT,
                theme_prompt TEXT NOT NULL,
                image_style_prompt TEXT NOT NULL,
                script_prompt TEXT NOT NULL,
                compilation_intro_prompt TEXT,
                deep_dive_outline_prompt TEXT,
                voice_id TEXT DEFAULT 'en-US-AnaNeural',
                voice_style TEXT,
                music_folder TEXT,
                default_duration INTEGER DEFAULT 14,
                is_active BOOLEAN DEFAULT 1,
                videos_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Videos table (extended)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_type_id INTEGER,
                video_format_id INTEGER,
                youtube_account_id INTEGER,

                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                progress_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,

                -- Theme/concept data (flexible JSON for different content types)
                theme_data TEXT,
                scene_count INTEGER DEFAULT 1,

                -- Legacy fields for backward compatibility
                location TEXT,
                time_of_day TEXT,
                mood TEXT,
                detail TEXT,
                memory_hook TEXT,

                -- Generated content
                title TEXT,
                image_prompt TEXT,
                voiceover_script TEXT,
                screen_text TEXT,

                -- File paths
                image_path TEXT,
                voice_path TEXT,
                music_path TEXT,
                output_path TEXT,
                thumbnail_path TEXT,

                -- Video meta
                duration_seconds REAL,
                file_size_bytes INTEGER,
                error_message TEXT,

                -- YouTube data
                youtube_id TEXT,
                youtube_url TEXT,
                youtube_status TEXT,
                youtube_published_at TIMESTAMP,
                youtube_title TEXT,
                youtube_description TEXT,

                FOREIGN KEY (content_type_id) REFERENCES content_types(id),
                FOREIGN KEY (video_format_id) REFERENCES video_formats(id),
                FOREIGN KEY (youtube_account_id) REFERENCES youtube_accounts(id)
            )
        """)

        # Scenes table for multi-scene videos
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                scene_order INTEGER NOT NULL,
                theme_data TEXT,
                image_prompt TEXT,
                voiceover_script TEXT,
                screen_text TEXT,
                duration_seconds REAL,
                image_path TEXT,
                voice_path TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            )
        """)

    # Run migrations for existing databases
    _migrate_db()


def _migrate_db():
    """Add new columns to existing databases."""
    with get_db() as conn:
        # Get existing columns in videos table
        cursor = conn.execute("PRAGMA table_info(videos)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # New columns to add to videos
        new_video_columns = [
            ("content_type_id", "INTEGER"),
            ("video_format_id", "INTEGER"),
            ("youtube_account_id", "INTEGER"),
            ("theme_data", "TEXT"),
            ("scene_count", "INTEGER DEFAULT 1"),
            ("title", "TEXT"),
            ("progress", "INTEGER DEFAULT 0"),
            ("progress_message", "TEXT"),
            ("thumbnail_path", "TEXT"),
            ("file_size_bytes", "INTEGER"),
            ("youtube_id", "TEXT"),
            ("youtube_url", "TEXT"),
            ("youtube_status", "TEXT"),
            ("youtube_published_at", "TIMESTAMP"),
            ("youtube_title", "TEXT"),
            ("youtube_description", "TEXT"),
        ]

        for col_name, col_type in new_video_columns:
            if col_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE videos ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass

        # Check content_types table for new columns
        cursor = conn.execute("PRAGMA table_info(content_types)")
        ct_columns = {row[1] for row in cursor.fetchall()}

        ct_new_columns = [
            ("videos_count", "INTEGER DEFAULT 0"),
            ("compilation_intro_prompt", "TEXT"),
            ("deep_dive_outline_prompt", "TEXT"),
        ]

        for col_name, col_type in ct_new_columns:
            if col_name not in ct_columns:
                try:
                    conn.execute(f"ALTER TABLE content_types ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass


# ============== Users ==============

def create_user(username: str, password_hash: str, is_admin: bool = False) -> int:
    """Create a new user."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO users (username, password_hash, is_admin)
               VALUES (?, ?, ?)""",
            (username, password_hash, is_admin)
        )
        return cursor.lastrowid


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get a user by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        return dict(row) if row else None


def update_user_last_login(user_id: int) -> None:
    """Update user's last login timestamp."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id)
        )


def get_user_count() -> int:
    """Get total number of users."""
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ============== YouTube Accounts ==============

def create_youtube_account(name: str, credentials_path: str,
                           channel_id: str = None, channel_name: str = None) -> int:
    """Create a new YouTube account record."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO youtube_accounts
               (name, credentials_path, channel_id, channel_name)
               VALUES (?, ?, ?, ?)""",
            (name, credentials_path, channel_id, channel_name)
        )
        account_id = cursor.lastrowid

        # If this is the first account, make it default
        count = conn.execute("SELECT COUNT(*) FROM youtube_accounts").fetchone()[0]
        if count == 1:
            conn.execute(
                "UPDATE youtube_accounts SET is_default = 1 WHERE id = ?",
                (account_id,)
            )

        return account_id


def get_youtube_account(account_id: int) -> Optional[Dict[str, Any]]:
    """Get a YouTube account by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM youtube_accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_youtube_accounts() -> List[Dict[str, Any]]:
    """Get all YouTube accounts."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM youtube_accounts ORDER BY is_default DESC, created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_default_youtube_account() -> Optional[Dict[str, Any]]:
    """Get the default YouTube account."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM youtube_accounts WHERE is_default = 1"
        ).fetchone()
        return dict(row) if row else None


def set_default_youtube_account(account_id: int) -> None:
    """Set an account as the default."""
    with get_db() as conn:
        conn.execute("UPDATE youtube_accounts SET is_default = 0")
        conn.execute(
            "UPDATE youtube_accounts SET is_default = 1 WHERE id = ?",
            (account_id,)
        )


def update_youtube_account(account_id: int, **kwargs) -> None:
    """Update a YouTube account."""
    if not kwargs:
        return

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [account_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE youtube_accounts SET {fields} WHERE id = ?",
            values
        )


def delete_youtube_account(account_id: int) -> bool:
    """Delete a YouTube account."""
    with get_db() as conn:
        account = get_youtube_account(account_id)
        if not account:
            return False

        # Remove credentials file
        if account.get('credentials_path') and os.path.exists(account['credentials_path']):
            os.remove(account['credentials_path'])

        conn.execute("DELETE FROM youtube_accounts WHERE id = ?", (account_id,))

        # If deleted the default, set a new one
        if account.get('is_default'):
            remaining = conn.execute(
                "SELECT id FROM youtube_accounts ORDER BY created_at LIMIT 1"
            ).fetchone()
            if remaining:
                conn.execute(
                    "UPDATE youtube_accounts SET is_default = 1 WHERE id = ?",
                    (remaining[0],)
                )

        return True


def increment_account_publish_count(account_id: int) -> None:
    """Increment the videos_published count for an account."""
    with get_db() as conn:
        conn.execute(
            """UPDATE youtube_accounts
               SET videos_published = videos_published + 1,
                   last_used_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), account_id)
        )


# ============== Video Formats ==============

def create_video_format(slug: str, name: str, **kwargs) -> int:
    """Create a new video format."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO video_formats
               (slug, name, description, icon, min_duration, max_duration,
                target_duration, scene_count_min, scene_count_max, scene_count_default,
                script_style, needs_intro, needs_outro, transition_style, aspect_ratio, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                slug, name,
                kwargs.get('description', ''),
                kwargs.get('icon', ''),
                kwargs.get('min_duration', 10),
                kwargs.get('max_duration', 60),
                kwargs.get('target_duration', 15),
                kwargs.get('scene_count_min', 1),
                kwargs.get('scene_count_max', 1),
                kwargs.get('scene_count_default', 1),
                kwargs.get('script_style', 'micro'),
                kwargs.get('needs_intro', False),
                kwargs.get('needs_outro', False),
                kwargs.get('transition_style', 'cut'),
                kwargs.get('aspect_ratio', '9:16'),
                kwargs.get('is_active', True)
            )
        )
        return cursor.lastrowid


def get_video_format(format_id: int) -> Optional[Dict[str, Any]]:
    """Get a video format by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM video_formats WHERE id = ?",
            (format_id,)
        ).fetchone()
        return dict(row) if row else None


def get_video_format_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Get a video format by slug."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM video_formats WHERE slug = ?",
            (slug,)
        ).fetchone()
        return dict(row) if row else None


def get_all_video_formats() -> List[Dict[str, Any]]:
    """Get all video formats."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM video_formats ORDER BY target_duration"
        ).fetchall()
        return [dict(row) for row in rows]


def get_active_video_formats() -> List[Dict[str, Any]]:
    """Get only active video formats."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM video_formats WHERE is_active = 1 ORDER BY target_duration"
        ).fetchall()
        return [dict(row) for row in rows]


# ============== Content Types ==============

def create_content_type(slug: str, name: str, theme_prompt: str,
                        image_style_prompt: str, script_prompt: str,
                        **kwargs) -> int:
    """Create a new content type."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO content_types
               (slug, name, theme_prompt, image_style_prompt, script_prompt,
                description, icon, voice_id, voice_style, music_folder,
                default_duration, is_active, compilation_intro_prompt, deep_dive_outline_prompt)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                slug, name, theme_prompt, image_style_prompt, script_prompt,
                kwargs.get('description', ''),
                kwargs.get('icon', ''),
                kwargs.get('voice_id', 'en-US-AnaNeural'),
                kwargs.get('voice_style', ''),
                kwargs.get('music_folder', 'general'),
                kwargs.get('default_duration', 14),
                kwargs.get('is_active', True),
                kwargs.get('compilation_intro_prompt', ''),
                kwargs.get('deep_dive_outline_prompt', '')
            )
        )
        return cursor.lastrowid


def get_content_type(content_type_id: int) -> Optional[Dict[str, Any]]:
    """Get a content type by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM content_types WHERE id = ?",
            (content_type_id,)
        ).fetchone()
        return dict(row) if row else None


def get_content_type_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Get a content type by slug."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM content_types WHERE slug = ?",
            (slug,)
        ).fetchone()
        return dict(row) if row else None


def get_all_content_types() -> List[Dict[str, Any]]:
    """Get all content types."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM content_types ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]


def get_active_content_types() -> List[Dict[str, Any]]:
    """Get only active content types."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM content_types WHERE is_active = 1 ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]


def update_content_type(content_type_id: int, **kwargs) -> None:
    """Update a content type."""
    if not kwargs:
        return

    kwargs['updated_at'] = datetime.now().isoformat()

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [content_type_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE content_types SET {fields} WHERE id = ?",
            values
        )


def toggle_content_type(content_type_id: int) -> bool:
    """Toggle a content type's active status. Returns new status."""
    with get_db() as conn:
        current = conn.execute(
            "SELECT is_active FROM content_types WHERE id = ?",
            (content_type_id,)
        ).fetchone()

        if not current:
            return False

        new_status = not current[0]
        conn.execute(
            "UPDATE content_types SET is_active = ?, updated_at = ? WHERE id = ?",
            (new_status, datetime.now().isoformat(), content_type_id)
        )
        return new_status


def delete_content_type(content_type_id: int) -> bool:
    """Delete a content type (only if no videos reference it)."""
    with get_db() as conn:
        # Check for videos using this content type
        count = conn.execute(
            "SELECT COUNT(*) FROM videos WHERE content_type_id = ?",
            (content_type_id,)
        ).fetchone()[0]

        if count > 0:
            return False

        conn.execute("DELETE FROM content_types WHERE id = ?", (content_type_id,))
        return True


def increment_content_type_count(content_type_id: int) -> None:
    """Increment the videos_count for a content type."""
    with get_db() as conn:
        conn.execute(
            "UPDATE content_types SET videos_count = videos_count + 1 WHERE id = ?",
            (content_type_id,)
        )


# ============== Videos ==============

def create_video(content_type_id: int = None, video_format_id: int = None) -> int:
    """Create a new video record and return its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO videos (status, content_type_id, video_format_id) VALUES ('pending', ?, ?)",
            (content_type_id, video_format_id)
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


def update_progress(video_id: int, progress: int, message: str = None) -> None:
    """Update the progress of a video generation."""
    update_data = {'progress': progress}
    if message:
        update_data['progress_message'] = message
    update_video(video_id, **update_data)


def set_error(video_id: int, error_message: str) -> None:
    """Set an error message and mark video as failed."""
    update_video(video_id, status='failed', error_message=error_message)


def mark_complete(video_id: int, output_path: str, duration_seconds: float,
                  thumbnail_path: str = None, file_size_bytes: int = None) -> None:
    """Mark video as complete with output path and duration."""
    with get_db() as conn:
        # Get content_type_id first
        row = conn.execute(
            "SELECT content_type_id FROM videos WHERE id = ?",
            (video_id,)
        ).fetchone()
        content_type_id = row[0] if row else None

        # Build update data
        update_data = {
            'status': 'complete',
            'completed_at': datetime.now().isoformat(),
            'output_path': output_path,
            'duration_seconds': duration_seconds,
            'progress': 100,
            'progress_message': 'Complete!'
        }
        if thumbnail_path:
            update_data['thumbnail_path'] = thumbnail_path
        if file_size_bytes:
            update_data['file_size_bytes'] = file_size_bytes

        # Update video status
        fields = ", ".join(f"{k} = ?" for k in update_data.keys())
        values = list(update_data.values()) + [video_id]
        conn.execute(f"UPDATE videos SET {fields} WHERE id = ?", values)

        # Increment content type count in same transaction
        if content_type_id:
            conn.execute(
                "UPDATE content_types SET videos_count = videos_count + 1 WHERE id = ?",
                (content_type_id,)
            )


def get_video(video_id: int) -> Optional[Dict[str, Any]]:
    """Get a video by ID with content type and format info."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT v.*,
                      ct.name as content_type_name,
                      ct.slug as content_type_slug,
                      ct.icon as content_type_icon,
                      vf.name as format_name,
                      vf.slug as format_slug,
                      vf.icon as format_icon,
                      vf.aspect_ratio as format_aspect_ratio,
                      ya.name as youtube_account_name,
                      ya.channel_name as youtube_channel_name
               FROM videos v
               LEFT JOIN content_types ct ON v.content_type_id = ct.id
               LEFT JOIN video_formats vf ON v.video_format_id = vf.id
               LEFT JOIN youtube_accounts ya ON v.youtube_account_id = ya.id
               WHERE v.id = ?""",
            (video_id,)
        ).fetchone()
        return dict(row) if row else None


def get_recent_videos(limit: int = 20, content_type_id: int = None,
                      video_format_id: int = None) -> List[Dict[str, Any]]:
    """Get recent videos ordered by creation date, optionally filtered."""
    with get_db() as conn:
        query = """SELECT v.*,
                          ct.name as content_type_name,
                          ct.slug as content_type_slug,
                          ct.icon as content_type_icon,
                          vf.name as format_name,
                          vf.slug as format_slug,
                          vf.icon as format_icon
                   FROM videos v
                   LEFT JOIN content_types ct ON v.content_type_id = ct.id
                   LEFT JOIN video_formats vf ON v.video_format_id = vf.id
                   WHERE 1=1"""
        params = []

        if content_type_id:
            query += " AND v.content_type_id = ?"
            params.append(content_type_id)
        if video_format_id:
            query += " AND v.video_format_id = ?"
            params.append(video_format_id)

        query += " ORDER BY v.created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_all_videos(content_type_id: int = None, video_format_id: int = None) -> List[Dict[str, Any]]:
    """Get all videos ordered by creation date."""
    with get_db() as conn:
        query = """SELECT v.*,
                          ct.name as content_type_name,
                          ct.slug as content_type_slug,
                          ct.icon as content_type_icon,
                          vf.name as format_name,
                          vf.slug as format_slug,
                          vf.icon as format_icon
                   FROM videos v
                   LEFT JOIN content_types ct ON v.content_type_id = ct.id
                   LEFT JOIN video_formats vf ON v.video_format_id = vf.id
                   WHERE 1=1"""
        params = []

        if content_type_id:
            query += " AND v.content_type_id = ?"
            params.append(content_type_id)
        if video_format_id:
            query += " AND v.video_format_id = ?"
            params.append(video_format_id)

        query += " ORDER BY v.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def delete_video(video_id: int) -> bool:
    """Delete a video and its files."""
    video = get_video(video_id)
    if not video:
        return False

    # Delete files
    for path_field in ['image_path', 'voice_path', 'output_path', 'thumbnail_path']:
        path = video.get(path_field)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    # Delete scenes first
    with get_db() as conn:
        scenes = get_video_scenes(video_id)
        for scene in scenes:
            for path_field in ['image_path', 'voice_path']:
                path = scene.get(path_field)
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        conn.execute("DELETE FROM scenes WHERE video_id = ?", (video_id,))
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))

    return True


# ============== Scenes ==============

def create_scene(video_id: int, scene_order: int, **kwargs) -> int:
    """Create a new scene for a video."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO scenes
               (video_id, scene_order, theme_data, image_prompt, voiceover_script,
                screen_text, duration_seconds, image_path, voice_path, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                video_id, scene_order,
                json.dumps(kwargs.get('theme_data', {})) if kwargs.get('theme_data') else None,
                kwargs.get('image_prompt'),
                kwargs.get('voiceover_script'),
                kwargs.get('screen_text'),
                kwargs.get('duration_seconds'),
                kwargs.get('image_path'),
                kwargs.get('voice_path'),
                kwargs.get('status', 'pending')
            )
        )
        return cursor.lastrowid


def update_scene(scene_id: int, **kwargs) -> None:
    """Update a scene."""
    if not kwargs:
        return

    # Handle theme_data specially
    if 'theme_data' in kwargs and isinstance(kwargs['theme_data'], dict):
        kwargs['theme_data'] = json.dumps(kwargs['theme_data'])

    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [scene_id]

    with get_db() as conn:
        conn.execute(f"UPDATE scenes SET {fields} WHERE id = ?", values)


def get_scene(scene_id: int) -> Optional[Dict[str, Any]]:
    """Get a scene by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM scenes WHERE id = ?",
            (scene_id,)
        ).fetchone()
        if row:
            scene = dict(row)
            if scene.get('theme_data'):
                scene['theme_data'] = json.loads(scene['theme_data'])
            return scene
        return None


def get_video_scenes(video_id: int) -> List[Dict[str, Any]]:
    """Get all scenes for a video in order."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM scenes WHERE video_id = ? ORDER BY scene_order",
            (video_id,)
        ).fetchall()
        scenes = []
        for row in rows:
            scene = dict(row)
            if scene.get('theme_data'):
                try:
                    scene['theme_data'] = json.loads(scene['theme_data'])
                except:
                    pass
            scenes.append(scene)
        return scenes


def mark_scene_complete(scene_id: int, image_path: str = None,
                        voice_path: str = None, duration_seconds: float = None) -> None:
    """Mark a scene as complete."""
    update_data = {'status': 'complete'}
    if image_path:
        update_data['image_path'] = image_path
    if voice_path:
        update_data['voice_path'] = voice_path
    if duration_seconds:
        update_data['duration_seconds'] = duration_seconds
    update_scene(scene_id, **update_data)


def set_scene_error(scene_id: int, error_message: str) -> None:
    """Mark a scene as failed."""
    update_scene(scene_id, status='failed', error_message=error_message)


# ============== YouTube Functions ==============

def update_youtube_status(video_id: int, status: str) -> None:
    """Update the YouTube upload status of a video."""
    update_video(video_id, youtube_status=status)


def set_youtube_published(video_id: int, youtube_id: str, youtube_url: str,
                          title: str, description: str, account_id: int = None) -> None:
    """Mark video as published to YouTube."""
    update_video(
        video_id,
        youtube_id=youtube_id,
        youtube_url=youtube_url,
        youtube_status='published',
        youtube_published_at=datetime.now().isoformat(),
        youtube_title=title,
        youtube_description=description,
        youtube_account_id=account_id
    )

    if account_id:
        increment_account_publish_count(account_id)


def set_youtube_failed(video_id: int) -> None:
    """Mark YouTube upload as failed."""
    update_video(video_id, youtube_status='failed')


# ============== Theme Data Helpers ==============

def set_theme_data(video_id: int, theme: dict) -> None:
    """Store theme data as JSON."""
    update_video(video_id, theme_data=json.dumps(theme))


def get_theme_data(video_id: int) -> Optional[dict]:
    """Get theme data as dict."""
    video = get_video(video_id)
    if video and video.get('theme_data'):
        try:
            return json.loads(video['theme_data'])
        except:
            return None
    return None


# ============== Seed Data ==============

def seed_video_formats():
    """Create default video formats if none exist."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM video_formats").fetchone()[0]
        if count > 0:
            return

    # Short
    create_video_format(
        slug="short",
        name="Short",
        description="Quick vertical video for YouTube Shorts, TikTok, Reels",
        icon="play-icon",
        min_duration=10,
        max_duration=60,
        target_duration=15,
        scene_count_min=1,
        scene_count_max=1,
        scene_count_default=1,
        script_style="micro",
        needs_intro=False,
        needs_outro=False,
        transition_style="cut",
        aspect_ratio="9:16",
        is_active=True
    )

    # Compilation
    create_video_format(
        slug="compilation",
        name="Compilation",
        description="Collection of scenes with intro/outro (8-15 min)",
        icon="collection-icon",
        min_duration=300,
        max_duration=900,
        target_duration=600,
        scene_count_min=8,
        scene_count_max=20,
        scene_count_default=12,
        script_style="narrated",
        needs_intro=True,
        needs_outro=True,
        transition_style="crossfade",
        aspect_ratio="16:9",
        is_active=True
    )

    # Deep Dive
    create_video_format(
        slug="deep_dive",
        name="Deep Dive",
        description="Long-form essay with narration (10-20 min)",
        icon="film-icon",
        min_duration=600,
        max_duration=1200,
        target_duration=900,
        scene_count_min=10,
        scene_count_max=30,
        scene_count_default=15,
        script_style="essay",
        needs_intro=True,
        needs_outro=True,
        transition_style="crossfade",
        aspect_ratio="16:9",
        is_active=True
    )

    # Ambient
    create_video_format(
        slug="ambient",
        name="Ambient",
        description="Long background video with minimal narration (30-60 min)",
        icon="moon-icon",
        min_duration=1800,
        max_duration=3600,
        target_duration=2700,
        scene_count_min=30,
        scene_count_max=60,
        scene_count_default=45,
        script_style="minimal",
        needs_intro=True,
        needs_outro=False,
        transition_style="crossfade",
        aspect_ratio="16:9",
        is_active=True
    )


def seed_content_types():
    """Create default content types if none exist."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM content_types").fetchone()[0]
        if count > 0:
            return

    # Liminal Spaces
    create_content_type(
        slug="liminal",
        name="Liminal Spaces",
        icon="moon-icon",
        description="Empty, familiar places that feel slightly wrong",
        theme_prompt="""Generate a liminal space concept for a short atmospheric video.
Return JSON only:
{
  "location": "specific place with decade if relevant",
  "time": "specific late night time like 3:47 AM",
  "mood": "2-3 word emotional tone",
  "detail": "one small sensory detail like a sound or smell",
  "memory_hook": "vague nostalgic connection to childhood or past"
}

Make it feel familiar but slightly wrong. Draw from: hotels, malls, schools, pools, hospitals, airports, arcades, bowling alleys, parking garages, laundromats - all at off-hours or empty.""",
        image_style_prompt="liminal photography, low fluorescent lighting, empty, 1980s-1990s aesthetic, film grain, slightly unsettling, no people",
        script_prompt="Write second-person narration, 15-25 words max. Whispered tone. Present tense. Evoke vague memory or deja vu. No resolution or explanation.",
        compilation_intro_prompt="Write a 2-sentence intro for a compilation video about liminal spaces. Mysterious, inviting tone. Hint that viewers will recognize these places from dreams or memories.",
        deep_dive_outline_prompt="""Create an outline for a 10-15 minute essay about liminal spaces.
Include:
- What makes spaces feel 'liminal'
- Psychology of why they unsettle us
- Common examples and why they resonate
- The internet's fascination with liminal aesthetics
- Connection to memory and nostalgia

Return JSON with 'title', 'hook', and 'sections' array with 'title', 'key_points', 'duration_seconds'.""",
        voice_id="en-US-AnaNeural",
        voice_style="whispered, slow, contemplative",
        music_folder="liminal",
        default_duration=14,
        is_active=True
    )

    # Scary Facts
    create_content_type(
        slug="scary_facts",
        name="Scary Facts",
        icon="alert-icon",
        description="Unsettling true facts with dark visuals",
        theme_prompt="""Generate an unsettling but TRUE fact that most people don't know.
Return JSON only:
{
  "topic": "subject area (ocean, space, human body, nature, history, psychology)",
  "fact": "the disturbing fact in 1-2 clear sentences",
  "why_scary": "brief note on what makes this unsettling",
  "visual_concept": "what image would represent this eerily"
}

Make it genuinely creepy but factually accurate. No urban legends.""",
        image_style_prompt="dark, ominous, photorealistic, moody dramatic lighting, unsettling atmosphere, cinematic",
        script_prompt="State the fact directly with a short hook. Start with 'Scientists discovered...' or 'In the deep ocean...' or similar. Under 25 words total.",
        compilation_intro_prompt="Write a 2-sentence intro for a scary facts compilation. Ominous tone. Warn viewers these facts might disturb them.",
        deep_dive_outline_prompt="""Create an outline for a deep dive into a specific scary topic (choose one: deep ocean, space, human body, or psychology).

Return JSON with 'title', 'hook', 'topic', and 'sections' array with 'title', 'facts', 'visual_ideas', 'duration_seconds'.""",
        voice_id="en-GB-RyanNeural",
        voice_style="serious, slightly ominous, measured pace",
        music_folder="scary",
        default_duration=12,
        is_active=True
    )

    # 2-Sentence Horror
    create_content_type(
        slug="horror_stories",
        name="2-Sentence Horror",
        icon="ghost-icon",
        description="Micro horror stories with creepy visuals",
        theme_prompt="""Generate an original 2-sentence horror story.
Return JSON only:
{
  "story": "The complete 2-sentence horror story",
  "setting": "where this takes place",
  "visual_focus": "the key unsettling visual element",
  "time": "when this happens (usually night)"
}

Make it genuinely creepy with a twist or disturbing implication in the second sentence. Original only, no famous ones.""",
        image_style_prompt="horror atmosphere, dark shadows, unsettling, cinematic lighting, creepy, photorealistic",
        script_prompt="Read the 2-sentence story exactly as written. Pause slightly between sentences.",
        compilation_intro_prompt="Write a 2-sentence intro for a horror story compilation. Creepy, warning tone. Suggest viewers shouldn't watch alone.",
        deep_dive_outline_prompt="""Create an outline for a video exploring the art of micro-horror and 2-sentence scary stories.

Include history, techniques, famous examples (without copying them), and psychological impact.

Return JSON with 'title', 'hook', and 'sections' array.""",
        voice_id="en-GB-SoniaNeural",
        voice_style="soft, creepy, deliberate pacing with pause between sentences",
        music_folder="horror",
        default_duration=10,
        is_active=True
    )

    # Nostalgia
    create_content_type(
        slug="nostalgia",
        name="90s/2000s Nostalgia",
        icon="video-icon",
        description="Things from the 90s and 2000s that hit different",
        theme_prompt="""Generate a nostalgic memory from the 1990s or early 2000s that many people share.
Return JSON only:
{
  "thing": "the specific nostalgic thing (toy, experience, place, sound, etc.)",
  "era": "specific years like '1997-2002'",
  "sensory_detail": "a specific sensory memory associated with it",
  "emotional_hook": "why this hits emotionally",
  "visual": "how to represent this visually"
}

Focus on shared experiences: school, toys, early internet, TV, malls, etc.""",
        image_style_prompt="nostalgic, warm tones, 1990s-2000s aesthetic, slightly faded, retro, cozy feeling",
        script_prompt="Write in second person. Start with 'Remember when...' or 'You never forgot...'. Warm, wistful tone. 15-25 words.",
        compilation_intro_prompt="Write a 2-sentence intro for a 90s/2000s nostalgia compilation. Warm, inviting tone. Promise viewers a trip down memory lane.",
        deep_dive_outline_prompt="""Create an outline for a video about why 90s/2000s nostalgia is so powerful for millennials and Gen Z.

Cover: specific cultural touchstones, psychology of nostalgia, why this era specifically resonates.

Return JSON with 'title', 'hook', and 'sections' array.""",
        voice_id="en-US-JennyNeural",
        voice_style="warm, wistful, gentle smile in voice",
        music_folder="nostalgia",
        default_duration=14,
        is_active=True
    )

    # Shower Thoughts
    create_content_type(
        slug="shower_thoughts",
        name="Shower Thoughts",
        icon="droplet-icon",
        description="Mind-bending realizations and observations",
        theme_prompt="""Generate an original 'shower thought' - a mind-bending observation or realization.
Return JSON only:
{
  "thought": "the shower thought itself, one sentence",
  "category": "type: philosophical, wordplay, perspective shift, realization",
  "visual_concept": "an abstract or symbolic visual to accompany this"
}

Make it genuinely thought-provoking or perspective-shifting. Original only.""",
        image_style_prompt="abstract, surreal, dreamy, soft focus, contemplative mood, ethereal lighting",
        script_prompt="State the thought directly. No preamble. Let it land. Under 20 words.",
        compilation_intro_prompt="Write a 2-sentence intro for a shower thoughts compilation. Philosophical, slightly playful tone.",
        deep_dive_outline_prompt="""Create an outline for a video exploring the nature of 'shower thoughts' and why our brains generate insights in idle moments.

Return JSON with 'title', 'hook', and 'sections' array.""",
        voice_id="en-US-GuyNeural",
        voice_style="calm, contemplative, thoughtful pauses",
        music_folder="general",
        default_duration=10,
        is_active=True
    )
