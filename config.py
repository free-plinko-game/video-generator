"""Configuration settings for the Liminal Space Video Generator."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys (set via environment variables or .env file)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")

# Directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs/videos")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MUSIC_DIR = os.path.join(BASE_DIR, "assets/music_loops")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
DATABASE_PATH = os.path.join(BASE_DIR, "data/videos.db")

# Video settings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
DEFAULT_DURATION = 14
VOICE_VOLUME = 1.0
MUSIC_VOLUME = 0.3
DEFAULT_VOICE = "en-US-AnaNeural"

# Available voices for whispered narration
AVAILABLE_VOICES = [
    ("en-US-AnaNeural", "Ana (US, Female, Soft)"),
    ("en-GB-SoniaNeural", "Sonia (UK, Female)"),
    ("en-US-GuyNeural", "Guy (US, Male, Calm)"),
    ("en-AU-NatashaNeural", "Natasha (AU, Female)"),
    ("en-US-AriaNeural", "Aria (US, Female)"),
]

# Hugging Face model
HF_IMAGE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_IMAGE_MODEL}"

# Generation settings
IMAGE_WIDTH = 768   # SDXL supported dimensions (closest to 9:16)
IMAGE_HEIGHT = 1344
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds

# Create directories on import
for directory in [OUTPUT_DIR, ASSETS_DIR, MUSIC_DIR, TEMP_DIR, os.path.dirname(DATABASE_PATH)]:
    os.makedirs(directory, exist_ok=True)
