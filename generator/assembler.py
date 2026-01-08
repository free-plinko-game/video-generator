"""Video assembler using MoviePy to create the final video."""

import os
import sys
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip,
    TextClip, concatenate_audioclips, concatenate_videoclips, vfx, afx, AudioClip
)
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# Video dimensions for different formats
SHORTS_SIZE = (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)  # 1080x1920 (9:16)
LONGFORM_SIZE = (1920, 1080)  # 16:9 for compilations, deep dives, ambient


def create_ken_burns_clip(image_path: str, duration: float):
    """
    Create an image clip with Ken Burns effect (slow zoom).

    Args:
        image_path: Path to the image file
        duration: Duration of the clip in seconds

    Returns:
        ImageClip with Ken Burns zoom effect
    """
    # Load the image
    clip = ImageClip(image_path, duration=duration)

    # Ken Burns: zoom from 100% to 110% over duration
    start_scale = 1.0
    end_scale = 1.10

    def zoom_effect(get_frame, t):
        """Apply gradual zoom effect."""
        progress = t / duration
        scale = start_scale + (end_scale - start_scale) * progress

        frame = get_frame(t)

        # Calculate new dimensions
        h, w = frame.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)

        # Resize the frame
        from PIL import Image
        img = Image.fromarray(frame)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Crop to center
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        img = img.crop((left, top, left + w, top + h))

        return np.array(img)

    return clip.transform(zoom_effect)


def create_text_overlay(text: str, duration: float, video_size: tuple):
    """
    Create a text overlay for the video.

    Args:
        text: The text to display
        duration: Duration of the clip in seconds
        video_size: Tuple of (width, height)

    Returns:
        TextClip with fade in effect
    """
    # Use cross-platform font (DejaVu Sans works on Linux, fallback to Arial for Mac/Windows)
    import shutil
    if shutil.which('fc-list'):  # Linux
        font = 'DejaVu-Sans'
    else:
        font = 'Arial'

    # Create text clip
    txt_clip = TextClip(
        text=text,
        font_size=42,
        color='white',
        font=font,
        stroke_color='black',
        stroke_width=1,
        method='caption',
        size=(video_size[0] - 100, None),
        text_align='center'
    )

    # Position at bottom of screen (with more room) and set duration
    txt_clip = txt_clip.with_position(('center', video_size[1] - 350))
    txt_clip = txt_clip.with_duration(duration)

    # Add fade in effect (first 1.5 seconds)
    txt_clip = txt_clip.with_effects([vfx.CrossFadeIn(1.5)])

    return txt_clip


def assemble_short(
    image_path: str,
    voice_path: str,
    music_path: str,
    screen_text: str,
    output_path: str,
    voice_volume: float = None,
    music_volume: float = None,
    duration_padding: float = 5.0
) -> tuple:
    """
    Assemble a short-form video (YouTube Shorts format, 9:16).

    Args:
        image_path: Path to the generated image
        voice_path: Path to the voiceover audio
        music_path: Path to the music file (can be None)
        screen_text: Text to overlay on video
        output_path: Path to save the output video
        voice_volume: Volume for voice (0.0-1.0)
        music_volume: Volume for music (0.0-1.0)
        duration_padding: Seconds to add after voiceover ends

    Returns:
        tuple: (output_path, duration_seconds)
    """
    if voice_volume is None:
        voice_volume = config.VOICE_VOLUME
    if music_volume is None:
        music_volume = config.MUSIC_VOLUME

    # Load voiceover to get duration
    voice_audio = AudioFileClip(voice_path)
    voice_duration = voice_audio.duration

    # Add padding to video duration
    video_duration = voice_duration + duration_padding

    # Create the image clip with Ken Burns effect
    video_clip = create_ken_burns_clip(image_path, video_duration)
    video_clip = video_clip.with_fps(24)

    # Create text overlay
    text_overlay = create_text_overlay(
        screen_text,
        video_duration,
        (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
    )

    # Composite video with text
    final_video = CompositeVideoClip(
        [video_clip, text_overlay],
        size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
    )

    # Prepare audio tracks
    audio_tracks = []

    # Voice audio (at full volume or specified)
    voice_audio = voice_audio.with_volume_scaled(voice_volume)
    audio_tracks.append(voice_audio)

    # Music audio (if available)
    if music_path and os.path.exists(music_path):
        music_audio = AudioFileClip(music_path)

        # Loop music if shorter than video
        if music_audio.duration < video_duration:
            loops_needed = int(video_duration / music_audio.duration) + 1
            music_clips = [music_audio] * loops_needed
            music_audio = concatenate_audioclips(music_clips)

        # Trim to video length
        music_audio = music_audio.subclipped(0, video_duration)

        # Apply fade out (last 2 seconds)
        music_audio = music_audio.with_effects([afx.AudioFadeOut(2)])

        # Reduce volume
        music_audio = music_audio.with_volume_scaled(music_volume)

        audio_tracks.append(music_audio)

    # Combine audio tracks
    if len(audio_tracks) > 1:
        final_audio = CompositeAudioClip(audio_tracks)
        final_audio = final_audio.with_duration(video_duration)
    else:
        final_audio = audio_tracks[0]
        # Pad single audio track with silence if needed
        if final_audio.duration < video_duration:
            from moviepy import AudioClip
            silence = AudioClip(lambda t: 0, duration=video_duration - final_audio.duration)
            final_audio = concatenate_audioclips([final_audio, silence])

    # Set audio on video
    final_video = final_video.with_audio(final_audio)
    final_video = final_video.with_duration(video_duration)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Export video
    final_video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate='192k',
        preset='medium',
        threads=4,
        logger=None  # Suppress MoviePy output
    )

    # Clean up
    voice_audio.close()
    if music_path and os.path.exists(music_path):
        music_audio.close()
    final_video.close()

    return output_path, video_duration


def _prepare_music_track(music_path: str, duration: float, volume: float = None) -> AudioFileClip:
    """Prepare music track: loop if needed, trim to duration, fade out."""
    if volume is None:
        volume = config.MUSIC_VOLUME

    music_audio = AudioFileClip(music_path)

    # Loop music if shorter than video
    if music_audio.duration < duration:
        loops_needed = int(duration / music_audio.duration) + 1
        music_clips = [music_audio] * loops_needed
        music_audio = concatenate_audioclips(music_clips)

    # Trim to video length
    music_audio = music_audio.subclipped(0, duration)

    # Apply fade out (last 3 seconds)
    music_audio = music_audio.with_effects([afx.AudioFadeOut(3)])

    # Reduce volume
    music_audio = music_audio.with_volume_scaled(volume)

    return music_audio


def _create_silence(duration: float) -> AudioClip:
    """Create a silent audio clip."""
    return AudioClip(lambda t: 0, duration=duration)


def assemble_compilation(
    intro_image: str,
    intro_voice: str,
    scenes: list,
    outro_voice: str,
    music_path: str,
    output_path: str,
    transition_style: str = "crossfade",
    voice_volume: float = None,
    music_volume: float = None
) -> tuple:
    """
    Assemble a compilation video with multiple scenes.

    Args:
        intro_image: Path to intro/title card image
        intro_voice: Path to intro voiceover
        scenes: List of scene dicts with 'image', 'voice', 'text' keys
        outro_voice: Path to outro voiceover
        music_path: Path to background music
        output_path: Path to save output
        transition_style: 'crossfade' or 'cut'
        voice_volume: Volume for voice (0.0-1.0)
        music_volume: Volume for music (0.0-1.0)

    Returns:
        tuple: (output_path, duration_seconds)
    """
    if voice_volume is None:
        voice_volume = config.VOICE_VOLUME
    if music_volume is None:
        music_volume = config.MUSIC_VOLUME

    video_clips = []
    audio_clips = []
    current_time = 0
    transition_duration = 1.0 if transition_style == "crossfade" else 0

    # Intro segment
    intro_audio = AudioFileClip(intro_voice)
    intro_duration = intro_audio.duration + 2  # Add padding
    intro_clip = create_ken_burns_clip(intro_image, intro_duration)
    intro_clip = intro_clip.resized(LONGFORM_SIZE)
    intro_clip = intro_clip.with_fps(24)

    if transition_style == "crossfade":
        intro_clip = intro_clip.with_effects([vfx.CrossFadeOut(transition_duration)])

    video_clips.append(intro_clip)
    audio_clips.append(intro_audio.with_volume_scaled(voice_volume).with_start(current_time))
    current_time += intro_duration

    # Scene segments
    for i, scene in enumerate(scenes):
        scene_audio = AudioFileClip(scene['voice'])
        scene_duration = scene_audio.duration + 3  # Padding for pacing

        scene_clip = create_ken_burns_clip(scene['image'], scene_duration)
        scene_clip = scene_clip.resized(LONGFORM_SIZE)
        scene_clip = scene_clip.with_fps(24)

        # Add crossfade transitions
        if transition_style == "crossfade":
            scene_clip = scene_clip.with_effects([
                vfx.CrossFadeIn(transition_duration),
                vfx.CrossFadeOut(transition_duration)
            ])
            scene_clip = scene_clip.with_start(current_time - transition_duration)
        else:
            scene_clip = scene_clip.with_start(current_time)

        # Add text overlay if present
        if scene.get('text'):
            text_clip = create_text_overlay(scene['text'], scene_duration, LONGFORM_SIZE)
            text_clip = text_clip.with_start(scene_clip.start)
            scene_clip = CompositeVideoClip([scene_clip, text_clip], size=LONGFORM_SIZE)

        video_clips.append(scene_clip)
        audio_clips.append(scene_audio.with_volume_scaled(voice_volume).with_start(current_time))

        if transition_style == "crossfade":
            current_time += scene_duration - transition_duration
        else:
            current_time += scene_duration

    # Outro segment
    outro_audio = AudioFileClip(outro_voice)
    outro_duration = outro_audio.duration + 2

    # Use last scene image for outro background
    if scenes:
        outro_clip = create_ken_burns_clip(scenes[-1]['image'], outro_duration)
    else:
        outro_clip = create_ken_burns_clip(intro_image, outro_duration)

    outro_clip = outro_clip.resized(LONGFORM_SIZE)
    outro_clip = outro_clip.with_fps(24)

    if transition_style == "crossfade":
        outro_clip = outro_clip.with_effects([vfx.CrossFadeIn(transition_duration)])
        outro_clip = outro_clip.with_start(current_time - transition_duration)
    else:
        outro_clip = outro_clip.with_start(current_time)

    video_clips.append(outro_clip)
    audio_clips.append(outro_audio.with_volume_scaled(voice_volume).with_start(current_time))
    current_time += outro_duration

    total_duration = current_time

    # Combine video clips
    final_video = CompositeVideoClip(video_clips, size=LONGFORM_SIZE)
    final_video = final_video.with_duration(total_duration)

    # Combine audio
    voice_composite = CompositeAudioClip(audio_clips)
    voice_composite = voice_composite.with_duration(total_duration)

    # Add music
    if music_path and os.path.exists(music_path):
        music_audio = _prepare_music_track(music_path, total_duration, music_volume)
        final_audio = CompositeAudioClip([voice_composite, music_audio])
    else:
        final_audio = voice_composite

    final_audio = final_audio.with_duration(total_duration)
    final_video = final_video.with_audio(final_audio)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Export video
    final_video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate='192k',
        preset='medium',
        threads=4,
        logger=None
    )

    # Clean up
    final_video.close()
    for clip in video_clips:
        clip.close()
    for clip in audio_clips:
        clip.close()

    return output_path, total_duration


def assemble_deep_dive(
    scene_images: list,
    voice_path: str,
    music_path: str,
    output_path: str,
    voice_volume: float = None,
    music_volume: float = None
) -> tuple:
    """
    Assemble a deep dive/essay video with sections.

    Args:
        scene_images: List of dicts with 'image', 'duration', 'title' keys
        voice_path: Path to the complete voiceover
        music_path: Path to background music
        output_path: Path to save output
        voice_volume: Volume for voice (0.0-1.0)
        music_volume: Volume for music (0.0-1.0)

    Returns:
        tuple: (output_path, duration_seconds)
    """
    if voice_volume is None:
        voice_volume = config.VOICE_VOLUME
    if music_volume is None:
        music_volume = config.MUSIC_VOLUME * 0.7  # Lower for essay format

    # Load the main voiceover to get total duration
    voice_audio = AudioFileClip(voice_path)
    total_duration = voice_audio.duration + 5  # Add ending padding

    # Calculate duration per image based on total voice duration
    if scene_images:
        base_duration = total_duration / len(scene_images)
    else:
        base_duration = total_duration

    video_clips = []
    current_time = 0
    transition_duration = 2.0  # Longer crossfades for essay style

    for i, scene in enumerate(scene_images):
        # Use provided duration or calculate
        duration = scene.get('duration', base_duration)

        # Adjust final scene to fill remaining time
        if i == len(scene_images) - 1:
            duration = total_duration - current_time

        scene_clip = create_ken_burns_clip(scene['image'], duration)
        scene_clip = scene_clip.resized(LONGFORM_SIZE)
        scene_clip = scene_clip.with_fps(24)

        # Add crossfade
        scene_clip = scene_clip.with_effects([
            vfx.CrossFadeIn(transition_duration),
            vfx.CrossFadeOut(transition_duration)
        ])

        # Overlap for crossfade (except first clip)
        if i > 0:
            scene_clip = scene_clip.with_start(current_time - transition_duration)
            current_time += duration - transition_duration
        else:
            scene_clip = scene_clip.with_start(0)
            current_time += duration - transition_duration

        video_clips.append(scene_clip)

    # Combine video clips
    final_video = CompositeVideoClip(video_clips, size=LONGFORM_SIZE)
    final_video = final_video.with_duration(total_duration)

    # Prepare audio
    voice_audio = voice_audio.with_volume_scaled(voice_volume)

    if music_path and os.path.exists(music_path):
        music_audio = _prepare_music_track(music_path, total_duration, music_volume)
        final_audio = CompositeAudioClip([voice_audio, music_audio])
    else:
        final_audio = voice_audio

    # Pad audio if needed
    if final_audio.duration < total_duration:
        silence = _create_silence(total_duration - final_audio.duration)
        final_audio = concatenate_audioclips([final_audio, silence])

    final_audio = final_audio.with_duration(total_duration)
    final_video = final_video.with_audio(final_audio)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Export video
    final_video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate='192k',
        preset='medium',
        threads=4,
        logger=None
    )

    # Clean up
    voice_audio.close()
    final_video.close()
    for clip in video_clips:
        clip.close()

    return output_path, total_duration


def assemble_ambient(
    intro_image: str,
    intro_voice: str,
    scenes: list,
    music_path: str,
    output_path: str,
    transition_duration: float = 3.0,
    voice_volume: float = None,
    music_volume: float = None
) -> tuple:
    """
    Assemble a long ambient video with minimal narration.

    Args:
        intro_image: Path to intro image
        intro_voice: Path to short intro voiceover
        scenes: List of dicts with 'image', 'duration', 'text' keys
        music_path: Path to ambient music
        output_path: Path to save output
        transition_duration: Duration of crossfades between scenes
        voice_volume: Volume for voice (0.0-1.0)
        music_volume: Volume for music (0.0-1.0)

    Returns:
        tuple: (output_path, duration_seconds)
    """
    if voice_volume is None:
        voice_volume = config.VOICE_VOLUME
    if music_volume is None:
        music_volume = config.MUSIC_VOLUME * 1.2  # Music is more prominent in ambient

    video_clips = []
    current_time = 0

    # Intro with voiceover
    intro_audio = AudioFileClip(intro_voice)
    intro_duration = intro_audio.duration + 5  # Padding after intro

    intro_clip = create_ken_burns_clip(intro_image, intro_duration)
    intro_clip = intro_clip.resized(LONGFORM_SIZE)
    intro_clip = intro_clip.with_fps(24)
    intro_clip = intro_clip.with_effects([vfx.CrossFadeOut(transition_duration)])

    video_clips.append(intro_clip)
    current_time += intro_duration

    # All scene clips (ambient = just images, no per-scene voice)
    for i, scene in enumerate(scenes):
        duration = scene.get('duration', 60)

        scene_clip = create_ken_burns_clip(scene['image'], duration)
        scene_clip = scene_clip.resized(LONGFORM_SIZE)
        scene_clip = scene_clip.with_fps(24)

        # Smooth crossfades
        scene_clip = scene_clip.with_effects([
            vfx.CrossFadeIn(transition_duration),
            vfx.CrossFadeOut(transition_duration)
        ])

        # Overlap for crossfade
        scene_clip = scene_clip.with_start(current_time - transition_duration)
        current_time += duration - transition_duration

        video_clips.append(scene_clip)

    total_duration = current_time + transition_duration  # Account for final fade

    # Combine video clips
    final_video = CompositeVideoClip(video_clips, size=LONGFORM_SIZE)
    final_video = final_video.with_duration(total_duration)

    # Audio: intro voice + music
    intro_audio = intro_audio.with_volume_scaled(voice_volume)

    # Pad intro audio with silence
    intro_padded = concatenate_audioclips([
        intro_audio,
        _create_silence(total_duration - intro_audio.duration)
    ])

    if music_path and os.path.exists(music_path):
        music_audio = _prepare_music_track(music_path, total_duration, music_volume)
        final_audio = CompositeAudioClip([intro_padded, music_audio])
    else:
        final_audio = intro_padded

    final_audio = final_audio.with_duration(total_duration)
    final_video = final_video.with_audio(final_audio)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Export video (use faster preset for long videos)
    final_video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate='192k',
        preset='fast',  # Faster for long videos
        threads=4,
        logger=None
    )

    # Clean up
    intro_audio.close()
    final_video.close()
    for clip in video_clips:
        clip.close()

    return output_path, total_duration


# Backward compatibility alias
assemble_video = assemble_short


if __name__ == "__main__":
    # Test with placeholder files (would need actual files to run)
    print("Assembler module loaded successfully")
    print(f"Output directory: {config.OUTPUT_DIR}")
    print(f"Shorts dimensions: {SHORTS_SIZE}")
    print(f"Long-form dimensions: {LONGFORM_SIZE}")
