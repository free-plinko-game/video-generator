"""Music handler for selecting ambient/drone loops."""

import os
import random
from typing import Optional

import config


def get_random_music() -> Optional[str]:
    """
    Select a random music file from the music loops directory.

    Returns:
        str or None: Path to selected music file, or None if no music available
    """
    if not os.path.exists(config.MUSIC_DIR):
        return None

    # Get all audio files
    audio_extensions = ('.mp3', '.wav', '.ogg', '.m4a', '.flac')
    music_files = [
        f for f in os.listdir(config.MUSIC_DIR)
        if f.lower().endswith(audio_extensions) and not f.startswith('.')
    ]

    if not music_files:
        return None

    # Select random file
    selected = random.choice(music_files)
    return os.path.join(config.MUSIC_DIR, selected)


def get_music(selection: str = None) -> Optional[str]:
    """
    Get a music file based on selection.

    Args:
        selection: Music file name, 'random' for random selection,
                   'none' for no music, or None for random

    Returns:
        str or None: Path to selected music file, or None if no music
    """
    if selection == 'none':
        return None

    if selection is None or selection == 'random':
        return get_random_music()

    # Specific file selected
    music_path = os.path.join(config.MUSIC_DIR, selection)
    if os.path.exists(music_path):
        return music_path

    # Fallback to random if specified file doesn't exist
    return get_random_music()


def list_music_files() -> list:
    """
    List all available music files.

    Returns:
        list: List of music file names
    """
    if not os.path.exists(config.MUSIC_DIR):
        return []

    audio_extensions = ('.mp3', '.wav', '.ogg', '.m4a', '.flac')
    return [
        f for f in os.listdir(config.MUSIC_DIR)
        if f.lower().endswith(audio_extensions) and not f.startswith('.')
    ]


if __name__ == "__main__":
    # Test the handler
    music = get_random_music()
    if music:
        print(f"Selected music: {music}")
    else:
        print("No music files available")
    print(f"Available music: {list_music_files()}")
