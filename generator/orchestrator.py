"""Orchestrator for managing the full video generation pipeline."""

import os
import sys
import json
import traceback
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import db
from generator.theme_generator import generate_theme
from generator.prompt_generator import generate_prompts
from generator.image_generator import generate_image
from generator.voice_generator import generate_voice
from generator.music_handler import get_music
from generator.assembler import assemble_video


class VideoGenerationError(Exception):
    """Custom exception for video generation errors."""
    pass


def generate_video(content_type_id: int, video_id: int = None) -> dict:
    """
    Generate a complete video based on a content type.

    Args:
        content_type_id: ID of the content type to use
        video_id: Optional existing video ID to use (creates new if None)

    Returns:
        dict: Video record with all generated content

    Raises:
        VideoGenerationError: If any step fails
    """
    # Get content type configuration
    content_type = db.get_content_type(content_type_id)
    if not content_type:
        raise VideoGenerationError(f"Content type {content_type_id} not found")

    # Create database record if not provided
    if video_id is None:
        video_id = db.create_video(content_type_id)

    try:
        # Step 1: Generate theme using content type's prompt
        db.update_status(video_id, 'generating_theme')
        theme = generate_theme(content_type['theme_prompt'])

        # Save theme data as JSON
        db.set_theme_data(video_id, theme)

        # Also save legacy fields for backward compatibility (if applicable)
        if 'location' in theme:
            db.update_video(
                video_id,
                location=theme.get('location'),
                time_of_day=theme.get('time'),
                mood=theme.get('mood'),
                detail=theme.get('detail'),
                memory_hook=theme.get('memory_hook')
            )

        # Step 2: Generate prompts using content type's styles
        db.update_status(video_id, 'generating_prompts')
        prompts = generate_prompts(theme, content_type)

        # Save prompts to database
        db.update_video(
            video_id,
            image_prompt=prompts.get('image_prompt'),
            voiceover_script=prompts.get('voiceover_script'),
            screen_text=prompts.get('screen_text')
        )

        # Step 3: Generate image
        db.update_status(video_id, 'creating_image')
        image_path = os.path.join(config.TEMP_DIR, f"image_{video_id}.png")
        generate_image(prompts['image_prompt'], image_path)
        db.update_video(video_id, image_path=image_path)

        # Step 4: Generate voiceover using content type's voice
        db.update_status(video_id, 'creating_voice')
        voice_path = os.path.join(config.TEMP_DIR, f"voice_{video_id}.mp3")
        voice_id = content_type.get('voice_id', config.DEFAULT_VOICE)
        generate_voice(prompts['voiceover_script'], voice_path, voice_id)
        db.update_video(video_id, voice_path=voice_path)

        # Step 5: Select music from content type's folder
        db.update_status(video_id, 'selecting_music')
        music_folder = content_type.get('music_folder', 'general')
        music_path = get_music(music_folder)
        if music_path:
            db.update_video(video_id, music_path=music_path)

        # Step 6: Assemble video
        db.update_status(video_id, 'assembling')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(config.OUTPUT_DIR, f"video_{video_id}_{timestamp}.mp4")

        # Get duration padding from content type
        default_duration = content_type.get('default_duration', 14)
        duration_padding = max(2.0, default_duration - 10)  # Approximate padding

        output_path, duration = assemble_video(
            image_path=image_path,
            voice_path=voice_path,
            music_path=music_path,
            screen_text=prompts['screen_text'],
            output_path=output_path,
            duration_padding=duration_padding
        )

        # Step 7: Mark complete
        db.mark_complete(video_id, output_path, duration)

        return db.get_video(video_id)

    except Exception as e:
        # Log the error and mark as failed
        error_message = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        db.set_error(video_id, error_message)
        raise VideoGenerationError(f"Video generation failed: {str(e)}") from e


def get_status(video_id: int) -> dict:
    """
    Get the current status of a video generation.

    Args:
        video_id: ID of the video

    Returns:
        dict: Status information including status, progress percentage, and any error
    """
    video = db.get_video(video_id)
    if not video:
        return {'error': 'Video not found'}

    status = video['status']

    # Map status to progress percentage
    status_progress = {
        'pending': 0,
        'generating_theme': 10,
        'generating_prompts': 25,
        'creating_image': 40,
        'creating_voice': 60,
        'selecting_music': 75,
        'assembling': 85,
        'complete': 100,
        'failed': -1
    }

    progress = status_progress.get(status, 0)

    # Human-readable status messages
    status_messages = {
        'pending': 'Starting...',
        'generating_theme': 'Generating concept...',
        'generating_prompts': 'Creating prompts...',
        'creating_image': 'Generating image...',
        'creating_voice': 'Creating voiceover...',
        'selecting_music': 'Selecting music...',
        'assembling': 'Assembling video...',
        'complete': 'Complete!',
        'failed': 'Failed'
    }

    message = status_messages.get(status, 'Unknown status')

    result = {
        'video_id': video_id,
        'status': status,
        'progress': progress,
        'message': message,
        'content_type': video.get('content_type_name')
    }

    if status == 'complete':
        result['output_path'] = video['output_path']
        result['duration'] = video['duration_seconds']

    if status == 'failed':
        result['error'] = video['error_message']

    return result


if __name__ == "__main__":
    # Test the orchestrator
    print("Starting video generation...")
    print("Note: This requires a valid content type ID")
