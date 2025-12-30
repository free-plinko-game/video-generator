"""Orchestrator for managing the full video generation pipeline."""

import os
import traceback
from datetime import datetime

import config
import db
from theme_generator import generate_theme
from prompt_generator import generate_prompts
from image_generator import generate_image
from voice_generator import generate_voice
from music_handler import get_music
from assembler import assemble_video


# Duration presets (in seconds of padding after voiceover)
DURATION_PRESETS = {
    'short': 2.0,     # ~15 second videos
    'medium': 5.0,    # ~25 second videos (default)
    'long': 10.0,     # ~35 second videos
}


class VideoGenerationError(Exception):
    """Custom exception for video generation errors."""
    pass


def generate_video(video_id: int = None, options: dict = None) -> dict:
    """
    Generate a complete liminal space video.

    Args:
        video_id: Optional existing video ID to use (creates new if None)
        options: Optional dict with customization options:
            - voice: Voice ID to use for narration
            - location: Location type constraint
            - time: Time of day constraint
            - mood: Mood constraint
            - duration: 'short', 'medium', or 'long'
            - music: Music file name, 'random', or 'none'
            - custom_text: Custom screen text (overrides AI generation)
            - custom_theme: Fully custom theme text (skips AI theme generation)

    Returns:
        dict: Video record with all generated content

    Raises:
        VideoGenerationError: If any step fails
    """
    if options is None:
        options = {}

    # Create database record if not provided
    if video_id is None:
        video_id = db.create_video()

    try:
        # Step 1: Generate or use custom theme
        db.update_status(video_id, 'generating_theme')

        if options.get('custom_theme'):
            # Use fully custom theme
            theme = {
                'location': options.get('custom_theme'),
                'time': options.get('time', 'late night'),
                'mood': options.get('mood', 'liminal'),
                'detail': 'flickering fluorescent light',
                'memory_hook': 'a place you visited once, long ago'
            }
        else:
            # Generate with constraints
            constraints = {}
            if options.get('location'):
                constraints['location'] = options['location']
            if options.get('time'):
                constraints['time'] = options['time']
            if options.get('mood'):
                constraints['mood'] = options['mood']

            theme = generate_theme(constraints if constraints else None)

        # Save theme to database
        db.update_video(
            video_id,
            location=theme.get('location'),
            time_of_day=theme.get('time'),
            mood=theme.get('mood'),
            detail=theme.get('detail'),
            memory_hook=theme.get('memory_hook')
        )

        # Step 2: Generate prompts
        db.update_status(video_id, 'generating_prompts')
        prompts = generate_prompts(theme)

        # Override screen text if custom text provided
        if options.get('custom_text'):
            prompts['screen_text'] = options['custom_text']

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

        # Step 4: Generate voiceover
        db.update_status(video_id, 'creating_voice')
        voice_path = os.path.join(config.TEMP_DIR, f"voice_{video_id}.mp3")
        voice = options.get('voice', config.DEFAULT_VOICE)
        generate_voice(prompts['voiceover_script'], voice_path, voice)
        db.update_video(video_id, voice_path=voice_path)

        # Step 5: Select music
        db.update_status(video_id, 'selecting_music')
        music_selection = options.get('music', 'random')
        music_path = get_music(music_selection)
        if music_path:
            db.update_video(video_id, music_path=music_path)

        # Step 6: Assemble video
        db.update_status(video_id, 'assembling')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(config.OUTPUT_DIR, f"liminal_{video_id}_{timestamp}.mp4")

        # Get duration padding
        duration_preset = options.get('duration', 'medium')
        duration_padding = DURATION_PRESETS.get(duration_preset, 5.0)

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


def regenerate_video(video_id: int, voice: str = None) -> dict:
    """
    Regenerate a video using the same theme but new prompts/assets.

    Args:
        video_id: ID of the video to regenerate from
        voice: Optional voice ID to use for narration

    Returns:
        dict: New video record

    Raises:
        VideoGenerationError: If regeneration fails
    """
    # Get the original video
    original = db.get_video(video_id)
    if not original:
        raise VideoGenerationError(f"Video {video_id} not found")

    # Create a new video record
    new_video_id = db.create_video()

    try:
        # Copy theme from original
        db.update_video(
            new_video_id,
            location=original['location'],
            time_of_day=original['time_of_day'],
            mood=original['mood'],
            detail=original['detail'],
            memory_hook=original['memory_hook']
        )

        # Build theme dict for prompt generation
        theme = {
            'location': original['location'],
            'time': original['time_of_day'],
            'mood': original['mood'],
            'detail': original['detail'],
            'memory_hook': original['memory_hook']
        }

        # Generate new prompts
        db.update_status(new_video_id, 'generating_prompts')
        prompts = generate_prompts(theme)

        db.update_video(
            new_video_id,
            image_prompt=prompts.get('image_prompt'),
            voiceover_script=prompts.get('voiceover_script'),
            screen_text=prompts.get('screen_text')
        )

        # Generate new image
        db.update_status(new_video_id, 'creating_image')
        image_path = os.path.join(config.TEMP_DIR, f"image_{new_video_id}.png")
        generate_image(prompts['image_prompt'], image_path)
        db.update_video(new_video_id, image_path=image_path)

        # Generate new voiceover
        db.update_status(new_video_id, 'creating_voice')
        voice_path = os.path.join(config.TEMP_DIR, f"voice_{new_video_id}.mp3")
        generate_voice(prompts['voiceover_script'], voice_path, voice)
        db.update_video(new_video_id, voice_path=voice_path)

        # Select music
        db.update_status(new_video_id, 'selecting_music')
        music_path = get_random_music()
        if music_path:
            db.update_video(new_video_id, music_path=music_path)

        # Assemble video
        db.update_status(new_video_id, 'assembling')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(config.OUTPUT_DIR, f"liminal_{new_video_id}_{timestamp}.mp4")

        output_path, duration = assemble_video(
            image_path=image_path,
            voice_path=voice_path,
            music_path=music_path,
            screen_text=prompts['screen_text'],
            output_path=output_path
        )

        # Mark complete
        db.mark_complete(new_video_id, output_path, duration)

        return db.get_video(new_video_id)

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        db.set_error(new_video_id, error_message)
        raise VideoGenerationError(f"Video regeneration failed: {str(e)}") from e


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
        'generating_theme': 'Generating liminal concept...',
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
        'message': message
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
    try:
        video = generate_video()
        print(f"Video generated successfully!")
        print(f"Output: {video['output_path']}")
        print(f"Duration: {video['duration_seconds']}s")
    except VideoGenerationError as e:
        print(f"Generation failed: {e}")
