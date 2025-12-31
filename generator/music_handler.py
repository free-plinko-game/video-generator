"""Music handler for selecting ambient/drone loops by folder."""

import os
import random
import sys
from typing import Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.m4a', '.flac')


def get_music(folder_name: str = None, selection: str = None) -> Optional[str]:
    """
    Get a music file from the specified folder.

    Args:
        folder_name: Subfolder of music directory (e.g., 'liminal', 'scary')
        selection: Specific file name, 'random', 'none', or None for random

    Returns:
        str or None: Path to selected music file, or None if no music
    """
    if selection == 'none':
        return None

    # Determine the music directory
    if folder_name:
        music_dir = os.path.join(config.MUSIC_DIR, folder_name)
    else:
        music_dir = config.MUSIC_DIR

    # Fallback to general folder if specified folder doesn't exist or is empty
    if not os.path.exists(music_dir) or not _has_music_files(music_dir):
        music_dir = os.path.join(config.MUSIC_DIR, 'general')

    # If still no music, try the base music directory
    if not os.path.exists(music_dir) or not _has_music_files(music_dir):
        music_dir = config.MUSIC_DIR

    if not os.path.exists(music_dir):
        return None

    # Get all audio files
    music_files = [
        f for f in os.listdir(music_dir)
        if f.lower().endswith(AUDIO_EXTENSIONS) and not f.startswith('.')
    ]

    if not music_files:
        return None

    # Select specific file or random
    if selection and selection != 'random':
        if selection in music_files:
            return os.path.join(music_dir, selection)
        # If specific file not found, fall back to random

    # Random selection
    selected = random.choice(music_files)
    return os.path.join(music_dir, selected)


def _has_music_files(directory: str) -> bool:
    """Check if directory contains any music files."""
    if not os.path.exists(directory):
        return False
    for f in os.listdir(directory):
        if f.lower().endswith(AUDIO_EXTENSIONS) and not f.startswith('.'):
            return True
    return False


def list_music_files(folder_name: str = None) -> List[str]:
    """
    List all available music files in a folder.

    Args:
        folder_name: Subfolder of music directory, or None for all files

    Returns:
        list: List of music file names
    """
    if folder_name:
        music_dir = os.path.join(config.MUSIC_DIR, folder_name)
    else:
        music_dir = config.MUSIC_DIR

    if not os.path.exists(music_dir):
        return []

    files = []

    # If looking at base directory, include files from all subdirectories
    if folder_name is None:
        # Get files from base directory
        for f in os.listdir(music_dir):
            full_path = os.path.join(music_dir, f)
            if os.path.isfile(full_path) and f.lower().endswith(AUDIO_EXTENSIONS) and not f.startswith('.'):
                files.append(f)
            elif os.path.isdir(full_path):
                # Get files from subdirectory
                for sf in os.listdir(full_path):
                    if sf.lower().endswith(AUDIO_EXTENSIONS) and not sf.startswith('.'):
                        files.append(f"{f}/{sf}")
    else:
        files = [
            f for f in os.listdir(music_dir)
            if f.lower().endswith(AUDIO_EXTENSIONS) and not f.startswith('.')
        ]

    return sorted(files)


def list_music_folders() -> List[str]:
    """
    List all available music folders.

    Returns:
        list: List of folder names
    """
    if not os.path.exists(config.MUSIC_DIR):
        return []

    folders = [
        f for f in os.listdir(config.MUSIC_DIR)
        if os.path.isdir(os.path.join(config.MUSIC_DIR, f)) and not f.startswith('.')
    ]

    return sorted(folders)


if __name__ == "__main__":
    # Test the handler
    print(f"Music folders: {list_music_folders()}")
    print(f"All music files: {list_music_files()}")

    music = get_music('liminal')
    if music:
        print(f"Selected liminal music: {music}")
    else:
        print("No liminal music files available")

    music = get_music('general')
    if music:
        print(f"Selected general music: {music}")
    else:
        print("No general music files available")
