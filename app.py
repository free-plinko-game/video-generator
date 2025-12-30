"""Flask web application for Liminal Space Video Generator."""

import os
import threading
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, send_file, flash, session
)
from urllib.parse import urlencode

import config
import db
from orchestrator import generate_video, regenerate_video, get_status, VideoGenerationError
from voice_generator import get_available_voices
from music_handler import list_music_files
from theme_generator import LOCATION_TYPES, TIME_OPTIONS, MOOD_OPTIONS
from publisher import youtube

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Store active generation threads
active_generations = {}


def run_generation(video_id: int, options: dict = None):
    """Background thread function for video generation."""
    try:
        generate_video(video_id, options)
    except VideoGenerationError:
        pass  # Error is already logged to database
    finally:
        if video_id in active_generations:
            del active_generations[video_id]


def run_regeneration(original_id: int, voice: str = None):
    """Background thread function for video regeneration."""
    try:
        regenerate_video(original_id, voice)
    except VideoGenerationError:
        pass


def run_youtube_upload(video_id: int, title: str, description: str, tags: list, privacy: str):
    """Background thread function for YouTube upload."""
    try:
        video = db.get_video(video_id)
        if not video or not video.get('output_path'):
            db.set_youtube_failed(video_id)
            return

        db.update_youtube_status(video_id, 'uploading')

        result = youtube.upload_video(
            video_path=video['output_path'],
            title=title,
            description=description,
            tags=tags,
            privacy=privacy
        )

        db.set_youtube_published(
            video_id,
            youtube_id=result['id'],
            youtube_url=result['url'],
            title=title,
            description=description
        )
    except Exception as e:
        print(f"YouTube upload error: {e}")
        db.set_youtube_failed(video_id)


@app.route('/')
def dashboard():
    """Dashboard with generate button, progress, and recent videos."""
    recent_videos = db.get_recent_videos(12)
    return render_template(
        'dashboard.html',
        videos=recent_videos,
        location_types=LOCATION_TYPES,
        time_options=TIME_OPTIONS,
        mood_options=MOOD_OPTIONS,
        voices=get_available_voices(),
        music_files=list_music_files()
    )


@app.route('/generate', methods=['POST'])
def generate():
    """Trigger new video generation."""
    # Check if API keys are configured
    if not config.ANTHROPIC_API_KEY:
        flash('Please configure your Anthropic API key in Settings', 'error')
        return redirect(url_for('settings'))

    if not config.HF_API_TOKEN:
        flash('Please configure your Hugging Face API token in Settings', 'error')
        return redirect(url_for('settings'))

    # Build options from form data
    options = {
        'voice': request.form.get('voice', config.DEFAULT_VOICE),
        'location': request.form.get('location', 'random'),
        'time': request.form.get('time', 'random'),
        'mood': request.form.get('mood', 'random'),
        'duration': request.form.get('duration', 'medium'),
        'music': request.form.get('music', 'random'),
    }

    # Optional custom text/theme
    custom_text = request.form.get('custom_text', '').strip()
    if custom_text:
        options['custom_text'] = custom_text

    custom_theme = request.form.get('custom_theme', '').strip()
    if custom_theme:
        options['custom_theme'] = custom_theme

    # Create video record
    video_id = db.create_video()

    # Start generation in background thread
    thread = threading.Thread(target=run_generation, args=(video_id, options))
    thread.daemon = True
    thread.start()
    active_generations[video_id] = thread

    # Return JSON with video ID for status polling
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'video_id': video_id, 'status': 'started'})

    # Redirect to dashboard for non-AJAX requests
    return redirect(url_for('dashboard'))


@app.route('/status/<int:video_id>')
def status(video_id):
    """Return JSON with generation progress."""
    status_info = get_status(video_id)
    return jsonify(status_info)


@app.route('/videos')
def gallery():
    """Gallery of all generated videos."""
    videos = db.get_all_videos()
    return render_template('gallery.html', videos=videos)


@app.route('/videos/<int:video_id>')
def video_detail(video_id):
    """Single video detail page."""
    video = db.get_video(video_id)
    if not video:
        flash('Video not found', 'error')
        return redirect(url_for('gallery'))

    # Generate YouTube metadata if not already set
    youtube_metadata = None
    if video.get('status') == 'complete' and not video.get('youtube_title'):
        youtube_metadata = youtube.generate_video_metadata(video)

    return render_template(
        'video_detail.html',
        video=video,
        youtube_metadata=youtube_metadata,
        youtube_authenticated=youtube.is_authenticated()
    )


@app.route('/videos/<int:video_id>/download')
def download_video(video_id):
    """Download MP4 file."""
    video = db.get_video(video_id)
    if not video or not video.get('output_path'):
        flash('Video file not found', 'error')
        return redirect(url_for('gallery'))

    if not os.path.exists(video['output_path']):
        flash('Video file not found on disk', 'error')
        return redirect(url_for('video_detail', video_id=video_id))

    return send_file(
        video['output_path'],
        mimetype='video/mp4',
        as_attachment=True,
        download_name=f"liminal_{video_id}.mp4"
    )


@app.route('/videos/<int:video_id>/regenerate', methods=['POST'])
def regenerate(video_id):
    """Regenerate video with same theme."""
    original = db.get_video(video_id)
    if not original:
        flash('Original video not found', 'error')
        return redirect(url_for('gallery'))

    voice = request.form.get('voice', config.DEFAULT_VOICE)

    # Start regeneration in background
    thread = threading.Thread(target=run_regeneration, args=(video_id, voice))
    thread.daemon = True
    thread.start()

    flash('Regeneration started! Check the dashboard for progress.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/videos/<int:video_id>/publish', methods=['POST'])
def publish_to_youtube(video_id):
    """Publish video to YouTube."""
    if not youtube.is_authenticated():
        flash('Please connect your YouTube account in Settings first', 'error')
        return redirect(url_for('settings'))

    video = db.get_video(video_id)
    if not video:
        flash('Video not found', 'error')
        return redirect(url_for('gallery'))

    if video.get('status') != 'complete':
        flash('Video must be complete before publishing', 'error')
        return redirect(url_for('video_detail', video_id=video_id))

    # Get form data
    title = request.form.get('youtube_title', '').strip()
    description = request.form.get('youtube_description', '').strip()
    tags_str = request.form.get('youtube_tags', '')
    privacy = request.form.get('youtube_privacy', config.YOUTUBE_DEFAULT_PRIVACY)

    # Parse tags
    tags = [t.strip() for t in tags_str.split(',') if t.strip()]
    if not tags:
        tags = config.YOUTUBE_DEFAULT_TAGS

    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('video_detail', video_id=video_id))

    # Start upload in background
    thread = threading.Thread(
        target=run_youtube_upload,
        args=(video_id, title, description, tags, privacy)
    )
    thread.daemon = True
    thread.start()

    flash('YouTube upload started! This may take a few minutes.', 'success')
    return redirect(url_for('video_detail', video_id=video_id))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """API keys and preferences settings."""
    if request.method == 'POST':
        # Update environment variables (in-memory only)
        anthropic_key = request.form.get('anthropic_key', '').strip()
        hf_token = request.form.get('hf_token', '').strip()
        default_voice = request.form.get('default_voice', config.DEFAULT_VOICE)

        if anthropic_key:
            config.ANTHROPIC_API_KEY = anthropic_key
            os.environ['ANTHROPIC_API_KEY'] = anthropic_key

        if hf_token:
            config.HF_API_TOKEN = hf_token
            os.environ['HF_API_TOKEN'] = hf_token

        config.DEFAULT_VOICE = default_voice

        # Save to .env file for persistence
        env_path = os.path.join(config.BASE_DIR, '.env')
        env_content = f"""ANTHROPIC_API_KEY={config.ANTHROPIC_API_KEY}
HF_API_TOKEN={config.HF_API_TOKEN}
DEFAULT_VOICE={config.DEFAULT_VOICE}
"""
        with open(env_path, 'w') as f:
            f.write(env_content)

        flash('Settings saved successfully!', 'success')
        return redirect(url_for('settings'))

    # Get YouTube status
    youtube_authenticated = youtube.is_authenticated()
    youtube_channel = None
    if youtube_authenticated:
        youtube_channel = youtube.get_channel_info()

    return render_template(
        'settings.html',
        anthropic_key=config.ANTHROPIC_API_KEY,
        hf_token=config.HF_API_TOKEN,
        default_voice=config.DEFAULT_VOICE,
        available_voices=get_available_voices(),
        music_files=list_music_files(),
        youtube_authenticated=youtube_authenticated,
        youtube_channel=youtube_channel,
        client_secrets_exists=os.path.exists(config.GOOGLE_CLIENT_SECRETS_FILE)
    )


# YouTube OAuth routes

@app.route('/youtube/auth')
def youtube_auth():
    """Initiate YouTube OAuth flow."""
    if not os.path.exists(config.GOOGLE_CLIENT_SECRETS_FILE):
        flash('Please add client_secrets.json file first. See README for instructions.', 'error')
        return redirect(url_for('settings'))

    try:
        # Build the redirect URI
        redirect_uri = url_for('youtube_callback', _external=True)

        # Create flow
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            config.GOOGLE_CLIENT_SECRETS_FILE,
            scopes=config.YOUTUBE_SCOPES,
            redirect_uri=redirect_uri
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        # Store state in session
        session['oauth_state'] = state

        return redirect(authorization_url)

    except Exception as e:
        flash(f'Error starting OAuth flow: {str(e)}', 'error')
        return redirect(url_for('settings'))


@app.route('/youtube/callback')
def youtube_callback():
    """Handle YouTube OAuth callback."""
    try:
        # Get the authorization response
        redirect_uri = url_for('youtube_callback', _external=True)

        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            config.GOOGLE_CLIENT_SECRETS_FILE,
            scopes=config.YOUTUBE_SCOPES,
            redirect_uri=redirect_uri
        )

        # Fetch the token
        flow.fetch_token(authorization_response=request.url)

        # Save credentials
        creds = flow.credentials
        os.makedirs(os.path.dirname(config.YOUTUBE_CREDENTIALS_FILE), exist_ok=True)
        with open(config.YOUTUBE_CREDENTIALS_FILE, 'w') as f:
            f.write(creds.to_json())

        flash('YouTube account connected successfully!', 'success')

    except Exception as e:
        flash(f'Error connecting YouTube: {str(e)}', 'error')

    return redirect(url_for('settings'))


@app.route('/youtube/disconnect', methods=['POST'])
def youtube_disconnect():
    """Disconnect YouTube account."""
    if youtube.disconnect():
        flash('YouTube account disconnected', 'success')
    else:
        flash('Error disconnecting YouTube account', 'error')
    return redirect(url_for('settings'))


@app.route('/youtube/status')
def youtube_status():
    """Return YouTube auth status as JSON."""
    authenticated = youtube.is_authenticated()
    channel = youtube.get_channel_info() if authenticated else None

    return jsonify({
        'authenticated': authenticated,
        'channel': channel
    })


@app.route('/api/videos')
def api_videos():
    """API endpoint to get all videos as JSON."""
    videos = db.get_all_videos()
    return jsonify(videos)


@app.route('/api/videos/<int:video_id>')
def api_video(video_id):
    """API endpoint to get a single video as JSON."""
    video = db.get_video(video_id)
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    return jsonify(video)


@app.template_filter('status_badge')
def status_badge_filter(status):
    """Template filter to get bootstrap badge class for status."""
    badges = {
        'pending': 'secondary',
        'generating_theme': 'info',
        'generating_prompts': 'info',
        'creating_image': 'info',
        'creating_voice': 'info',
        'selecting_music': 'info',
        'assembling': 'warning',
        'complete': 'success',
        'failed': 'danger'
    }
    return badges.get(status, 'secondary')


@app.template_filter('format_duration')
def format_duration_filter(seconds):
    """Template filter to format duration as MM:SS."""
    if not seconds:
        return '--:--'
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


@app.template_filter('youtube_status_icon')
def youtube_status_icon_filter(status):
    """Template filter to get YouTube status icon."""
    icons = {
        'published': '<span class="text-success" title="Published">&#9679;</span>',
        'uploading': '<span class="text-warning" title="Uploading">&#9679;</span>',
        'failed': '<span class="text-danger" title="Upload Failed">&#9679;</span>',
    }
    return icons.get(status, '')


if __name__ == '__main__':
    # Initialize database
    db.init_db()

    # Allow OAuth over HTTP for local development
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)
