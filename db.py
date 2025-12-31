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
                youtube_account_id INTEGER,

                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,

                -- Theme/concept data (flexible JSON for different content types)
                theme_data TEXT,

                -- Legacy fields for backward compatibility
                location TEXT,
                time_of_day TEXT,
                mood TEXT,
                detail TEXT,
                memory_hook TEXT,

                -- Generated content
                image_prompt TEXT,
                voiceover_script TEXT,
                screen_text TEXT,

                -- File paths
                image_path TEXT,
                voice_path TEXT,
                music_path TEXT,
                output_path TEXT,

                -- Video meta
                duration_seconds REAL,
                error_message TEXT,

                -- YouTube data
                youtube_id TEXT,
                youtube_url TEXT,
                youtube_status TEXT,
                youtube_published_at TIMESTAMP,
                youtube_title TEXT,
                youtube_description TEXT,

                FOREIGN KEY (content_type_id) REFERENCES content_types(id),
                FOREIGN KEY (youtube_account_id) REFERENCES youtube_accounts(id)
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

        # New columns to add
        new_columns = [
            ("content_type_id", "INTEGER"),
            ("youtube_account_id", "INTEGER"),
            ("theme_data", "TEXT"),
            ("youtube_id", "TEXT"),
            ("youtube_url", "TEXT"),
            ("youtube_status", "TEXT"),
            ("youtube_published_at", "TIMESTAMP"),
            ("youtube_title", "TEXT"),
            ("youtube_description", "TEXT"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE videos ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

        # Check content_types table
        cursor = conn.execute("PRAGMA table_info(content_types)")
        ct_columns = {row[1] for row in cursor.fetchall()}

        if "videos_count" not in ct_columns:
            try:
                conn.execute("ALTER TABLE content_types ADD COLUMN videos_count INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass


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
                default_duration, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                slug, name, theme_prompt, image_style_prompt, script_prompt,
                kwargs.get('description', ''),
                kwargs.get('icon', ''),
                kwargs.get('voice_id', 'en-US-AnaNeural'),
                kwargs.get('voice_style', ''),
                kwargs.get('music_folder', 'general'),
                kwargs.get('default_duration', 14),
                kwargs.get('is_active', True)
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

def create_video(content_type_id: int = None) -> int:
    """Create a new video record and return its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO videos (status, content_type_id) VALUES ('pending', ?)",
            (content_type_id,)
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
    with get_db() as conn:
        conn.execute(
            """UPDATE videos SET
               status = 'complete',
               completed_at = ?,
               output_path = ?,
               duration_seconds = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), output_path, duration_seconds, video_id)
        )

        # Increment content type count
        video = get_video(video_id)
        if video and video.get('content_type_id'):
            increment_content_type_count(video['content_type_id'])


def get_video(video_id: int) -> Optional[Dict[str, Any]]:
    """Get a video by ID with content type info."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT v.*,
                      ct.name as content_type_name,
                      ct.slug as content_type_slug,
                      ct.icon as content_type_icon,
                      ya.name as youtube_account_name,
                      ya.channel_name as youtube_channel_name
               FROM videos v
               LEFT JOIN content_types ct ON v.content_type_id = ct.id
               LEFT JOIN youtube_accounts ya ON v.youtube_account_id = ya.id
               WHERE v.id = ?""",
            (video_id,)
        ).fetchone()
        return dict(row) if row else None


def get_recent_videos(limit: int = 20, content_type_id: int = None) -> List[Dict[str, Any]]:
    """Get recent videos ordered by creation date, optionally filtered by content type."""
    with get_db() as conn:
        if content_type_id:
            rows = conn.execute(
                """SELECT v.*,
                          ct.name as content_type_name,
                          ct.slug as content_type_slug,
                          ct.icon as content_type_icon
                   FROM videos v
                   LEFT JOIN content_types ct ON v.content_type_id = ct.id
                   WHERE v.content_type_id = ?
                   ORDER BY v.created_at DESC LIMIT ?""",
                (content_type_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT v.*,
                          ct.name as content_type_name,
                          ct.slug as content_type_slug,
                          ct.icon as content_type_icon
                   FROM videos v
                   LEFT JOIN content_types ct ON v.content_type_id = ct.id
                   ORDER BY v.created_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(row) for row in rows]


def get_all_videos(content_type_id: int = None) -> List[Dict[str, Any]]:
    """Get all videos ordered by creation date."""
    with get_db() as conn:
        if content_type_id:
            rows = conn.execute(
                """SELECT v.*,
                          ct.name as content_type_name,
                          ct.slug as content_type_slug,
                          ct.icon as content_type_icon
                   FROM videos v
                   LEFT JOIN content_types ct ON v.content_type_id = ct.id
                   WHERE v.content_type_id = ?
                   ORDER BY v.created_at DESC""",
                (content_type_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT v.*,
                          ct.name as content_type_name,
                          ct.slug as content_type_slug,
                          ct.icon as content_type_icon
                   FROM videos v
                   LEFT JOIN content_types ct ON v.content_type_id = ct.id
                   ORDER BY v.created_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]


def delete_video(video_id: int) -> bool:
    """Delete a video and its files."""
    video = get_video(video_id)
    if not video:
        return False

    # Delete files
    for path_field in ['image_path', 'voice_path', 'output_path']:
        path = video.get(path_field)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    with get_db() as conn:
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))

    return True


# YouTube-specific functions

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


# Theme data helpers

def set_theme_data(video_id: int, theme: dict) -> None:
    """Store theme data as JSON."""
    update_video(video_id, theme_data=json.dumps(theme))


def get_theme_data(video_id: int) -> Optional[dict]:
    """Get theme data as dict."""
    video = get_video(video_id)
    if video and video.get('theme_data'):
        return json.loads(video['theme_data'])
    return None


# ============== Seed Data ==============

def seed_content_types():
    """Create default content types if none exist."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM content_types").fetchone()[0]
        if count > 0:
            return  # Already seeded

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
        image_style_prompt="liminal photography, low fluorescent lighting, empty, 1980s-1990s aesthetic, film grain, slightly unsettling, no people, vertical 9:16 composition",
        script_prompt="Write second-person narration, 15-25 words max. Whispered tone. Present tense. Evoke vague memory or deja vu. No resolution or explanation.",
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
        image_style_prompt="dark, ominous, photorealistic, moody dramatic lighting, unsettling atmosphere, cinematic, vertical 9:16 composition",
        script_prompt="State the fact directly with a short hook. Start with 'Scientists discovered...' or 'In the deep ocean...' or similar. Under 25 words total.",
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
        image_style_prompt="horror atmosphere, dark shadows, unsettling, cinematic lighting, creepy, photorealistic, vertical 9:16 composition",
        script_prompt="Read the 2-sentence story exactly as written. Pause slightly between sentences.",
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
        image_style_prompt="nostalgic, warm tones, 1990s-2000s aesthetic, slightly faded, retro, cozy feeling, vertical 9:16 composition",
        script_prompt="Write in second person. Start with 'Remember when...' or 'You never forgot...'. Warm, wistful tone. 15-25 words.",
        voice_id="en-US-JennyNeural",
        voice_style="warm, wistful, gentle smile in voice",
        music_folder="nostalgia",
        default_duration=14,
        is_active=False
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
        image_style_prompt="abstract, surreal, dreamy, soft focus, contemplative mood, ethereal lighting, vertical 9:16 composition",
        script_prompt="State the thought directly. No preamble. Let it land. Under 20 words.",
        voice_id="en-US-GuyNeural",
        voice_style="calm, contemplative, slight pause after for effect",
        music_folder="general",
        default_duration=10,
        is_active=False
    )
