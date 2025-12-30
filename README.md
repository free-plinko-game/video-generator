# Liminal Space Video Generator

An AI-powered application that generates atmospheric liminal space videos with eerie visuals, whispered narration, and ambient music.

## What It Creates

The generator produces short (15-20 second) vertical videos featuring:
- AI-generated liminal space imagery (empty hotels, abandoned malls, quiet pools)
- Second-person whispered narration evoking vague memories
- Slow Ken Burns zoom effect
- Atmospheric text overlays
- Ambient background music

## Features

- **One-Click Generation**: Generate complete videos with a single button click
- **Real-Time Progress**: Watch the generation pipeline progress in real-time
- **Video Gallery**: Browse all generated videos with metadata
- **Regeneration**: Create variations using the same theme
- **Dark Theme UI**: Aesthetic interface matching the liminal vibe

## Requirements

- Python 3.9+
- FFmpeg (for video processing)
- Anthropic API key
- Hugging Face API token

## Installation

### 1. Install FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

### 2. Clone and Install Dependencies

```bash
git clone <repository-url>
cd video-generator
pip install -r requirements.txt
```

### 3. Get API Keys

**Anthropic API Key:**
1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create an account and get your API key
3. Key format: `sk-ant-...`

**Hugging Face API Token:**
1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Create a new access token with read permissions
3. Token format: `hf_...`

### 4. Configure API Keys

You can configure keys in one of two ways:

**Option A: Environment Variables**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export HF_API_TOKEN="hf_..."
```

**Option B: Create a .env file**
```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
echo 'HF_API_TOKEN=hf_...' >> .env
```

**Option C: Use the Settings Page**
Configure keys directly in the web UI at `/settings`

### 5. Add Music (Optional)

Place ambient/drone music loops in `assets/music_loops/`:
```
assets/music_loops/
  dark_ambient_01.mp3
  drone_loop.mp3
  eerie_pad.mp3
```

Supported formats: MP3, WAV, OGG, M4A, FLAC

### 6. Run the Application

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Usage

1. **Generate**: Click "Generate New Video" on the dashboard
2. **Wait**: Watch the progress bar as the AI creates your video
3. **View**: Browse the video detail page with all metadata
4. **Download**: Download the MP4 file
5. **Regenerate**: Create variations with "Regenerate Similar"

## Project Structure

```
video-generator/
├── app.py              # Flask web application
├── config.py           # Configuration settings
├── db.py               # Database operations
├── theme_generator.py  # Claude-powered theme generation
├── prompt_generator.py # Claude-powered prompt generation
├── image_generator.py  # Hugging Face image generation
├── voice_generator.py  # Edge-TTS voice synthesis
├── music_handler.py    # Music selection
├── assembler.py        # MoviePy video assembly
├── orchestrator.py     # Pipeline orchestration
├── templates/          # HTML templates
├── static/             # Static assets
├── assets/
│   └── music_loops/    # Ambient music files
├── outputs/
│   └── videos/         # Generated videos
├── temp/               # Temporary files
├── data/
│   └── videos.db       # SQLite database
├── requirements.txt
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard with recent videos |
| `/generate` | POST | Start new video generation |
| `/status/<id>` | GET | Get generation progress |
| `/videos` | GET | Video gallery |
| `/videos/<id>` | GET | Video detail page |
| `/videos/<id>/download` | GET | Download video |
| `/settings` | GET/POST | Configure settings |

## Troubleshooting

### "Model is loading" / 503 errors
The Hugging Face model may need to warm up. The app will automatically retry.

### FFmpeg not found
Ensure FFmpeg is installed and in your PATH:
```bash
ffmpeg -version
```

### Font errors in video assembly
Install system fonts:
```bash
# Ubuntu
sudo apt install fonts-dejavu

# macOS - fonts should work out of the box
```

### API rate limits
Both Anthropic and Hugging Face have rate limits. Wait a moment and try again.

## Tech Stack

- **Backend**: Flask (Python)
- **AI Text**: Claude (Anthropic)
- **AI Images**: Stable Diffusion XL (Hugging Face)
- **Voice**: Edge-TTS (Microsoft)
- **Video**: MoviePy + FFmpeg
- **Database**: SQLite
- **Frontend**: Bootstrap 5

## License

MIT License
