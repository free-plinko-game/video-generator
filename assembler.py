"""Video assembler using MoviePy to create the final video."""

import os
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip,
    TextClip, concatenate_audioclips
)
import numpy as np

import config


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
    # Create text clip
    txt_clip = TextClip(
        text=text,
        font_size=42,
        color='white',
        font='Arial',
        stroke_color='black',
        stroke_width=1,
        method='caption',
        size=(video_size[0] - 100, None),
        text_align='center'
    )

    # Position at bottom of screen and set duration
    txt_clip = txt_clip.with_position(('center', video_size[1] - 200))
    txt_clip = txt_clip.with_duration(duration)

    # Add fade in effect (first 1.5 seconds)
    txt_clip = txt_clip.with_effects([lambda clip: clip.crossfadein(1.5)])

    return txt_clip


def assemble_video(
    image_path: str,
    voice_path: str,
    music_path: str,
    screen_text: str,
    output_path: str,
    voice_volume: float = None,
    music_volume: float = None
) -> tuple:
    """
    Assemble the final video from components.

    Args:
        image_path: Path to the generated image
        voice_path: Path to the voiceover audio
        music_path: Path to the music file (can be None)
        screen_text: Text to overlay on video
        output_path: Path to save the output video
        voice_volume: Volume for voice (0.0-1.0)
        music_volume: Volume for music (0.0-1.0)

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

    # Add padding to video duration (2-3 seconds after voiceover)
    video_duration = voice_duration + 2.5

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
        music_audio = music_audio.audio_fadeout(2)

        # Reduce volume
        music_audio = music_audio.with_volume_scaled(music_volume)

        audio_tracks.append(music_audio)

    # Combine audio tracks
    if len(audio_tracks) > 1:
        final_audio = CompositeAudioClip(audio_tracks)
    else:
        final_audio = audio_tracks[0]

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


if __name__ == "__main__":
    # Test with placeholder files (would need actual files to run)
    print("Assembler module loaded successfully")
    print(f"Output directory: {config.OUTPUT_DIR}")
    print(f"Video dimensions: {config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}")
