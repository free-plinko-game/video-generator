"""Voice generator using edge-tts for text-to-speech narration."""

import asyncio
import sys
import os
import edge_tts

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


async def _generate_voice_async(text: str, output_path: str, voice: str) -> str:
    """
    Async implementation of voice generation.

    Args:
        text: The text to convert to speech
        output_path: Path to save the audio file
        voice: The voice ID to use

    Returns:
        str: Path to the saved audio file
    """
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path


def generate_voice(text: str, output_path: str, voice: str = None) -> str:
    """
    Generate voice narration from text using edge-tts.

    Args:
        text: The text to convert to speech
        output_path: Path to save the audio file (MP3)
        voice: The voice ID to use (optional, defaults to config.DEFAULT_VOICE)

    Returns:
        str: Path to the saved audio file
    """
    if voice is None:
        voice = config.DEFAULT_VOICE

    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_generate_voice_async(text, output_path, voice))
    finally:
        loop.close()

    return result


def get_available_voices() -> list:
    """
    Get list of available voices for narration.

    Returns:
        list: List of tuples (voice_id, display_name)
    """
    return config.AVAILABLE_VOICES


if __name__ == "__main__":
    # Test the generator
    test_text = "You've been here before. The hum of the lights, the distant echo. It feels like a memory you can't quite place."
    output = generate_voice(test_text, "test_voice.mp3")
    print(f"Voice saved to: {output}")
