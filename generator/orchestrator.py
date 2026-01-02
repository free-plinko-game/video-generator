"""Orchestrator for managing the full video generation pipeline."""

import os
import sys
import json
import time
import traceback
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import db
from generator.theme_generator import generate_theme
from generator.prompt_generator import generate_prompts
from generator.script_generator import generate_intro_script, generate_outro_script, generate_long_script, generate_outline
from generator.image_generator import generate_image
from generator.voice_generator import generate_voice
from generator.music_handler import get_music
from generator.assembler import assemble_short, assemble_compilation, assemble_deep_dive, assemble_ambient


class VideoGenerationError(Exception):
    """Custom exception for video generation errors."""
    pass


# Rate limiting delay for image generation
IMAGE_GENERATION_DELAY = 2  # seconds


def generate_video(content_type_id: int, video_format_id: int, video_id: int = None) -> dict:
    """
    Main entry point for video generation.

    Routes to the appropriate pipeline based on format.
    """
    # Get content type and format
    content_type = db.get_content_type(content_type_id)
    if not content_type:
        raise VideoGenerationError(f"Content type {content_type_id} not found")

    video_format = db.get_video_format(video_format_id)
    if not video_format:
        raise VideoGenerationError(f"Video format {video_format_id} not found")

    # Create database record if not provided
    if video_id is None:
        video_id = db.create_video(content_type_id, video_format_id)

    try:
        format_slug = video_format['slug']

        if format_slug == "short":
            generate_short(video_id, content_type, video_format)
        elif format_slug == "compilation":
            generate_compilation(video_id, content_type, video_format)
        elif format_slug == "deep_dive":
            generate_deep_dive_video(video_id, content_type, video_format)
        elif format_slug == "ambient":
            generate_ambient_video(video_id, content_type, video_format)
        else:
            raise VideoGenerationError(f"Unknown format: {format_slug}")

        return db.get_video(video_id)

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        db.set_error(video_id, error_message)
        raise VideoGenerationError(f"Video generation failed: {str(e)}") from e


def generate_short(video_id: int, content_type: dict, video_format: dict):
    """Generate a single-scene short video."""

    # Step 1: Generate theme
    db.update_progress(video_id, 10, "Generating theme...")
    theme = generate_theme(content_type['theme_prompt'])
    db.set_theme_data(video_id, theme)

    # Save legacy fields for backward compatibility
    if 'location' in theme:
        db.update_video(
            video_id,
            location=theme.get('location'),
            time_of_day=theme.get('time'),
            mood=theme.get('mood'),
            detail=theme.get('detail'),
            memory_hook=theme.get('memory_hook')
        )

    # Step 2: Generate prompts
    db.update_progress(video_id, 20, "Creating prompts...")
    prompts = generate_prompts(theme, content_type)
    db.update_video(
        video_id,
        image_prompt=prompts.get('image_prompt'),
        voiceover_script=prompts.get('voiceover_script'),
        screen_text=prompts.get('screen_text')
    )

    # Step 3: Generate image (9:16 for shorts)
    db.update_progress(video_id, 40, "Generating image...")
    image_path = os.path.join(config.TEMP_DIR, f"image_{video_id}.png")
    generate_image(prompts['image_prompt'], image_path, aspect_ratio="9:16")
    db.update_video(video_id, image_path=image_path)

    # Step 4: Generate voiceover
    db.update_progress(video_id, 60, "Generating voiceover...")
    voice_path = os.path.join(config.TEMP_DIR, f"voice_{video_id}.mp3")
    voice_id = content_type.get('voice_id', config.DEFAULT_VOICE)
    generate_voice(prompts['voiceover_script'], voice_path, voice_id)
    db.update_video(video_id, voice_path=voice_path)

    # Step 5: Select music
    db.update_progress(video_id, 70, "Selecting music...")
    music_folder = content_type.get('music_folder', 'general')
    music_path = get_music(music_folder)
    if music_path:
        db.update_video(video_id, music_path=music_path)

    # Step 6: Assemble video
    db.update_progress(video_id, 80, "Assembling video...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(config.OUTPUT_DIR, f"short_{video_id}_{timestamp}.mp4")

    duration_padding = max(2.0, content_type.get('default_duration', 14) - 10)

    output_path, duration = assemble_short(
        image_path=image_path,
        voice_path=voice_path,
        music_path=music_path,
        screen_text=prompts.get('screen_text'),
        output_path=output_path,
        duration_padding=duration_padding
    )

    # Get file size
    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else None

    # Mark complete
    db.mark_complete(video_id, output_path, duration, file_size_bytes=file_size)


def generate_compilation(video_id: int, content_type: dict, video_format: dict):
    """Generate a compilation video with multiple scenes."""

    scene_count = video_format.get('scene_count_default', 12)
    db.update_video(video_id, scene_count=scene_count)

    # Step 1: Generate compilation theme/title
    db.update_progress(video_id, 5, "Creating compilation theme...")
    compilation_theme = generate_theme(content_type['theme_prompt'])
    compilation_theme['scene_count'] = scene_count
    compilation_theme['format'] = 'compilation'
    db.set_theme_data(video_id, compilation_theme)

    # Generate title
    title = f"{scene_count} {content_type['name']}"
    if 'location' in compilation_theme:
        title = f"{scene_count} {compilation_theme.get('mood', '')} {content_type['name']}"
    db.update_video(video_id, title=title)

    # Step 2: Generate intro
    db.update_progress(video_id, 8, "Generating intro...")
    intro_prompt = content_type.get('compilation_intro_prompt',
        f"Write a 2-sentence intro for a compilation video about {content_type['name']}.")
    intro_script = generate_intro_script(intro_prompt, content_type, compilation_theme)

    intro_voice_path = os.path.join(config.TEMP_DIR, f"intro_voice_{video_id}.mp3")
    generate_voice(intro_script, intro_voice_path, content_type.get('voice_id', config.DEFAULT_VOICE))

    # Generate intro image
    intro_image_prompt = f"{content_type['image_style_prompt']}, title card, {content_type['name']}, cinematic, 16:9 composition"
    intro_image_path = os.path.join(config.TEMP_DIR, f"intro_image_{video_id}.png")
    generate_image(intro_image_prompt, intro_image_path, aspect_ratio="16:9")

    # Step 3: Generate each scene
    scenes = []
    for i in range(scene_count):
        progress = 10 + int((i / scene_count) * 70)
        db.update_progress(video_id, progress, f"Generating scene {i+1}/{scene_count}...")

        # Create scene record
        scene_id = db.create_scene(video_id, i)

        try:
            # Generate scene theme
            scene_theme = generate_theme(content_type['theme_prompt'])
            db.update_scene(scene_id, theme_data=scene_theme)

            # Generate scene prompts
            scene_prompts = generate_prompts(scene_theme, content_type, aspect_ratio="16:9")
            db.update_scene(scene_id,
                image_prompt=scene_prompts['image_prompt'],
                voiceover_script=scene_prompts['voiceover_script'],
                screen_text=scene_prompts.get('screen_text', ''))

            # Generate scene image
            scene_image_path = os.path.join(config.TEMP_DIR, f"scene_{video_id}_{i}.png")
            generate_image(scene_prompts['image_prompt'], scene_image_path, aspect_ratio="16:9")

            # Generate scene voiceover
            scene_voice_path = os.path.join(config.TEMP_DIR, f"scene_voice_{video_id}_{i}.mp3")
            generate_voice(scene_prompts['voiceover_script'], scene_voice_path,
                          content_type.get('voice_id', config.DEFAULT_VOICE))

            # Mark scene complete
            db.mark_scene_complete(scene_id, scene_image_path, scene_voice_path)

            scenes.append({
                'image': scene_image_path,
                'voice': scene_voice_path,
                'text': scene_prompts.get('screen_text', ''),
                'script': scene_prompts['voiceover_script']
            })

            # Rate limiting
            time.sleep(IMAGE_GENERATION_DELAY)

        except Exception as e:
            db.set_scene_error(scene_id, str(e))
            # Continue with other scenes
            continue

    if len(scenes) < 3:
        raise VideoGenerationError(f"Only generated {len(scenes)} scenes, need at least 3")

    # Step 4: Generate outro
    db.update_progress(video_id, 82, "Generating outro...")
    outro_script = generate_outro_script(content_type)
    outro_voice_path = os.path.join(config.TEMP_DIR, f"outro_voice_{video_id}.mp3")
    generate_voice(outro_script, outro_voice_path, content_type.get('voice_id', config.DEFAULT_VOICE))

    # Step 5: Select music
    db.update_progress(video_id, 85, "Selecting music...")
    music_folder = content_type.get('music_folder', 'general')
    music_path = get_music(music_folder)
    if music_path:
        db.update_video(video_id, music_path=music_path)

    # Step 6: Assemble compilation
    db.update_progress(video_id, 90, "Assembling compilation...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(config.OUTPUT_DIR, f"compilation_{video_id}_{timestamp}.mp4")

    output_path, duration = assemble_compilation(
        intro_image=intro_image_path,
        intro_voice=intro_voice_path,
        scenes=scenes,
        outro_voice=outro_voice_path,
        music_path=music_path,
        output_path=output_path,
        transition_style=video_format.get('transition_style', 'crossfade')
    )

    # Generate thumbnail
    thumbnail_path = os.path.join(config.THUMBNAIL_DIR, f"thumb_{video_id}.png")
    # Use intro image as thumbnail for now
    if os.path.exists(intro_image_path):
        import shutil
        os.makedirs(config.THUMBNAIL_DIR, exist_ok=True)
        shutil.copy(intro_image_path, thumbnail_path)

    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
    db.mark_complete(video_id, output_path, duration, thumbnail_path, file_size)


def generate_deep_dive_video(video_id: int, content_type: dict, video_format: dict):
    """Generate a long-form essay video."""

    # Step 1: Generate outline
    db.update_progress(video_id, 5, "Creating outline...")
    outline_prompt = content_type.get('deep_dive_outline_prompt',
        f"Create an outline for a 10-15 minute essay about {content_type['name']}.")
    outline = generate_outline(outline_prompt, content_type)
    db.set_theme_data(video_id, outline)

    title = outline.get('title', f"Deep Dive: {content_type['name']}")
    db.update_video(video_id, title=title)

    # Step 2: Generate full script from outline
    db.update_progress(video_id, 10, "Writing full script...")
    full_script = generate_long_script(outline, content_type)
    db.update_video(video_id, voiceover_script=full_script)

    # Parse script into sections
    sections = outline.get('sections', [])
    scene_count = len(sections)
    db.update_video(video_id, scene_count=scene_count)

    # Step 3: Generate images for each section
    scene_images = []
    for i, section in enumerate(sections):
        progress = 15 + int((i / len(sections)) * 50)
        db.update_progress(video_id, progress, f"Generating visuals {i+1}/{len(sections)}...")

        scene_id = db.create_scene(video_id, i)

        try:
            # Generate image prompt from section
            section_title = section.get('title', f"Section {i+1}")
            image_prompt = f"{content_type['image_style_prompt']}, {section_title}, cinematic, 16:9 composition"

            scene_image_path = os.path.join(config.TEMP_DIR, f"deep_{video_id}_{i}.png")
            generate_image(image_prompt, scene_image_path, aspect_ratio="16:9")

            duration_seconds = section.get('duration_seconds', 60)

            db.mark_scene_complete(scene_id, scene_image_path, duration_seconds=duration_seconds)

            scene_images.append({
                'image': scene_image_path,
                'duration': duration_seconds,
                'title': section_title
            })

            time.sleep(IMAGE_GENERATION_DELAY)

        except Exception as e:
            db.set_scene_error(scene_id, str(e))
            continue

    if len(scene_images) < 3:
        raise VideoGenerationError(f"Only generated {len(scene_images)} section images, need at least 3")

    # Step 4: Generate full voiceover
    db.update_progress(video_id, 70, "Generating voiceover...")
    voice_path = os.path.join(config.TEMP_DIR, f"deep_voice_{video_id}.mp3")
    generate_voice(full_script, voice_path, content_type.get('voice_id', config.DEFAULT_VOICE))
    db.update_video(video_id, voice_path=voice_path)

    # Step 5: Select music
    db.update_progress(video_id, 75, "Selecting music...")
    music_folder = content_type.get('music_folder', 'general')
    music_path = get_music(music_folder)
    if music_path:
        db.update_video(video_id, music_path=music_path)

    # Step 6: Assemble video
    db.update_progress(video_id, 80, "Assembling video...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(config.OUTPUT_DIR, f"deep_dive_{video_id}_{timestamp}.mp4")

    output_path, duration = assemble_deep_dive(
        scene_images=scene_images,
        voice_path=voice_path,
        music_path=music_path,
        output_path=output_path
    )

    # Thumbnail
    thumbnail_path = os.path.join(config.THUMBNAIL_DIR, f"thumb_{video_id}.png")
    if scene_images and os.path.exists(scene_images[0]['image']):
        import shutil
        os.makedirs(config.THUMBNAIL_DIR, exist_ok=True)
        shutil.copy(scene_images[0]['image'], thumbnail_path)

    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
    db.mark_complete(video_id, output_path, duration, thumbnail_path, file_size)


def generate_ambient_video(video_id: int, content_type: dict, video_format: dict):
    """Generate a long ambient video with minimal narration."""

    scene_count = video_format.get('scene_count_default', 45)
    target_duration = video_format.get('target_duration', 2700)  # 45 minutes
    seconds_per_scene = target_duration // scene_count

    db.update_video(video_id, scene_count=scene_count)

    # Step 1: Generate intro
    db.update_progress(video_id, 5, "Generating intro...")
    intro_theme = generate_theme(content_type['theme_prompt'])
    db.set_theme_data(video_id, intro_theme)

    title = f"Ambient {content_type['name']} | {target_duration // 60} Minutes"
    db.update_video(video_id, title=title)

    # Generate intro voiceover (short)
    intro_script = f"Welcome. Let yourself drift through these {content_type['name'].lower()}. No need to focus. Just... exist."
    intro_voice_path = os.path.join(config.TEMP_DIR, f"ambient_intro_{video_id}.mp3")
    generate_voice(intro_script, intro_voice_path, content_type.get('voice_id', config.DEFAULT_VOICE))

    # Generate intro image
    intro_image_prompt = f"{content_type['image_style_prompt']}, establishing shot, wide angle, atmospheric, 16:9 composition"
    intro_image_path = os.path.join(config.TEMP_DIR, f"ambient_intro_img_{video_id}.png")
    generate_image(intro_image_prompt, intro_image_path, aspect_ratio="16:9")

    # Step 2: Generate all scene images
    scenes = []
    for i in range(scene_count):
        progress = 10 + int((i / scene_count) * 80)
        db.update_progress(video_id, progress, f"Generating scene {i+1}/{scene_count}...")

        scene_id = db.create_scene(video_id, i)

        try:
            # Generate theme for variety
            scene_theme = generate_theme(content_type['theme_prompt'])
            prompts = generate_prompts(scene_theme, content_type, aspect_ratio="16:9")

            scene_image_path = os.path.join(config.TEMP_DIR, f"ambient_{video_id}_{i}.png")
            generate_image(prompts['image_prompt'], scene_image_path, aspect_ratio="16:9")

            db.update_scene(scene_id,
                theme_data=scene_theme,
                image_prompt=prompts['image_prompt'],
                screen_text=prompts.get('screen_text', ''))

            db.mark_scene_complete(scene_id, scene_image_path, duration_seconds=seconds_per_scene)

            scenes.append({
                'image': scene_image_path,
                'duration': seconds_per_scene,
                'text': prompts.get('screen_text', '')
            })

            time.sleep(IMAGE_GENERATION_DELAY)

        except Exception as e:
            db.set_scene_error(scene_id, str(e))
            continue

    if len(scenes) < 10:
        raise VideoGenerationError(f"Only generated {len(scenes)} scenes, need at least 10 for ambient")

    # Step 3: Select music
    db.update_progress(video_id, 92, "Preparing audio...")
    music_folder = content_type.get('music_folder', 'general')
    music_path = get_music(music_folder)
    if music_path:
        db.update_video(video_id, music_path=music_path)

    # Step 4: Assemble ambient video
    db.update_progress(video_id, 95, "Assembling video...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(config.OUTPUT_DIR, f"ambient_{video_id}_{timestamp}.mp4")

    output_path, duration = assemble_ambient(
        intro_image=intro_image_path,
        intro_voice=intro_voice_path,
        scenes=scenes,
        music_path=music_path,
        output_path=output_path,
        transition_duration=3.0
    )

    # Thumbnail
    thumbnail_path = os.path.join(config.THUMBNAIL_DIR, f"thumb_{video_id}.png")
    if os.path.exists(intro_image_path):
        import shutil
        os.makedirs(config.THUMBNAIL_DIR, exist_ok=True)
        shutil.copy(intro_image_path, thumbnail_path)

    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
    db.mark_complete(video_id, output_path, duration, thumbnail_path, file_size)


def get_status(video_id: int) -> dict:
    """Get the current status of a video generation."""
    video = db.get_video(video_id)
    if not video:
        return {'error': 'Video not found'}

    result = {
        'video_id': video_id,
        'status': video['status'],
        'progress': video.get('progress', 0),
        'message': video.get('progress_message', ''),
        'content_type': video.get('content_type_name'),
        'format': video.get('format_name'),
        'scene_count': video.get('scene_count', 1)
    }

    if video['status'] == 'complete':
        result['output_path'] = video['output_path']
        result['duration'] = video['duration_seconds']
        result['file_size'] = video.get('file_size_bytes')

    if video['status'] == 'failed':
        result['error'] = video['error_message']

    # For multi-scene videos, include scene progress
    if video.get('scene_count', 1) > 1:
        scenes = db.get_video_scenes(video_id)
        completed_scenes = sum(1 for s in scenes if s['status'] == 'complete')
        result['scenes_completed'] = completed_scenes
        result['scenes_total'] = len(scenes)

    return result


if __name__ == "__main__":
    print("Content Factory Orchestrator")
    print("Run via app.py for web interface")
