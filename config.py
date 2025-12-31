"""Configuration settings for the Content Factory."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys (set via environment variables or .env file)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")

# Directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.path.join(DATA_DIR, "factory.db")
CREDENTIALS_DIR = os.path.join(DATA_DIR, "credentials")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs/videos")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# Video settings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
DEFAULT_DURATION = 14
VOICE_VOLUME = 1.0
MUSIC_VOLUME = 0.3
DEFAULT_VOICE = "en-US-AnaNeural"

# Available voices for narration
AVAILABLE_VOICES = [
    ("en-US-AnaNeural", "Ana (US, Female, Soft)"),
    ("en-US-GuyNeural", "Guy (US, Male, Calm)"),
    ("en-GB-SoniaNeural", "Sonia (UK, Female, Soft)"),
    ("en-GB-RyanNeural", "Ryan (UK, Male, Serious)"),
    ("en-AU-NatashaNeural", "Natasha (AU, Female)"),
    ("en-US-JennyNeural", "Jenny (US, Female, Neutral)"),
    ("en-US-AriaNeural", "Aria (US, Female)"),
]

# Hugging Face model
HF_IMAGE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_IMAGE_MODEL}"

# Generation settings
IMAGE_WIDTH = 768   # SDXL supported dimensions (closest to 9:16)
IMAGE_HEIGHT = 1344
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds

# YouTube API settings
GOOGLE_CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "client_secrets.json")
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

# Default YouTube upload settings
YOUTUBE_DEFAULT_PRIVACY = "public"  # "public", "private", or "unlisted"
YOUTUBE_DEFAULT_CATEGORY = "22"  # 22 = People & Blogs
YOUTUBE_DEFAULT_TAGS = ["shorts", "viral", "fyp"]
YOUTUBE_AUTO_PUBLISH = False  # Auto-publish after video generation

# Create directories on import
for directory in [OUTPUT_DIR, ASSETS_DIR, MUSIC_DIR, TEMP_DIR, DATA_DIR, CREDENTIALS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Create music subfolders
MUSIC_FOLDERS = ["liminal", "scary", "horror", "nostalgia", "general"]
for folder in MUSIC_FOLDERS:
    os.makedirs(os.path.join(MUSIC_DIR, folder), exist_ok=True)
