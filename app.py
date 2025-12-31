"""Flask web application for Content Factory - Multi-Format Video Generator."""

import os
import threading
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, send_file, flash, session
)
from urllib.parse import urlencode

import config
import db
from generator import generate_video, get_status, VideoGenerationError
from generator.voice_generator import get_available_voices
from generator.music_handler import list_music_files, list_music_folders
from publisher import youtube

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Store active generation threads
active_generations = {}


def run_generation(video_id: int, content_type_id: int):
    """Background thread function for video generation."""
    try:
        generate_video(content_type_id, video_id)
    except VideoGenerationError:
        pass  # Error is already logged to database
    finally:
        if video_id in active_generations:
            del active_generations[video_id]


def run_youtube_upload(video_id: int, account_id: int, title: str, description: str, tags: list, privacy: str):
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
            privacy=privacy,
            account_id=account_id
        )

        db.set_youtube_published(
            video_id,
            youtube_id=result['id'],
            youtube_url=result['url'],
            title=title,
            description=description,
            account_id=account_id
        )
    except Exception as e:
        print(f"YouTube upload error: {e}")
        db.set_youtube_failed(video_id)


# ============== Dashboard ==============

@app.route('/')
def dashboard():
    """Dashboard with content type selector and recent videos."""
    content_types = db.get_active_content_types()
    recent_videos = db.get_recent_videos(12)
    return render_template(
        'dashboard.html',
        content_types=content_types,
        videos=recent_videos
    )


@app.route('/generate', methods=['POST'])
def generate():
    """Trigger new video generation for a content type."""
    # Check if API keys are configured
    if not config.ANTHROPIC_API_KEY:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Please configure your Anthropic API key in Settings'}), 400
        flash('Please configure your Anthropic API key in Settings', 'error')
        return redirect(url_for('settings'))

    if not config.HF_API_TOKEN:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Please configure your Hugging Face API token in Settings'}), 400
        flash('Please configure your Hugging Face API token in Settings', 'error')
        return redirect(url_for('settings'))

    # Get content type ID
    content_type_id = request.form.get('content_type_id', type=int)
    if not content_type_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Please select a content type'}), 400
        flash('Please select a content type', 'error')
        return redirect(url_for('dashboard'))

    # Verify content type exists
    content_type = db.get_content_type(content_type_id)
    if not content_type:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Content type not found'}), 404
        flash('Content type not found', 'error')
        return redirect(url_for('dashboard'))

    # Create video record
    video_id = db.create_video(content_type_id)

    # Start generation in background thread
    thread = threading.Thread(target=run_generation, args=(video_id, content_type_id))
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


# ============== Videos ==============

@app.route('/videos')
def gallery():
    """Gallery of all generated videos."""
    videos = db.get_all_videos()
    content_types = db.get_all_content_types()
    return render_template('gallery.html', videos=videos, content_types=content_types)


@app.route('/videos/<int:video_id>')
def video_detail(video_id):
    """Single video detail page."""
    video = db.get_video(video_id)
    if not video:
        flash('Video not found', 'error')
        return redirect(url_for('gallery'))

    # Get YouTube accounts for publishing
    youtube_accounts = db.get_all_youtube_accounts()

    # Generate YouTube metadata if not already set
    youtube_metadata = None
    if video.get('status') == 'complete' and not video.get('youtube_title'):
        youtube_metadata = youtube.generate_video_metadata(video)

    return render_template(
        'video_detail.html',
        video=video,
        youtube_metadata=youtube_metadata,
        youtube_accounts=youtube_accounts
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

    # Generate filename from content type
    content_type_slug = video.get('content_type_slug', 'video')
    filename = f"{content_type_slug}_{video_id}.mp4"

    return send_file(
        video['output_path'],
        mimetype='video/mp4',
        as_attachment=True,
        download_name=filename
    )


@app.route('/videos/<int:video_id>/regenerate', methods=['POST'])
def regenerate(video_id):
    """Regenerate video with same content type."""
    original = db.get_video(video_id)
    if not original:
        flash('Original video not found', 'error')
        return redirect(url_for('gallery'))

    content_type_id = original.get('content_type_id')
    if not content_type_id:
        flash('Cannot regenerate: no content type', 'error')
        return redirect(url_for('video_detail', video_id=video_id))

    # Create new video and start generation
    new_video_id = db.create_video(content_type_id)
    thread = threading.Thread(target=run_generation, args=(new_video_id, content_type_id))
    thread.daemon = True
    thread.start()
    active_generations[new_video_id] = thread

    flash('Regeneration started! Check the dashboard for progress.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/videos/<int:video_id>/publish', methods=['POST'])
def publish_to_youtube(video_id):
    """Publish video to YouTube."""
    # Get account ID
    account_id = request.form.get('youtube_account_id', type=int)
    if not account_id:
        # Try default account
        default_account = db.get_default_youtube_account()
        if default_account:
            account_id = default_account['id']
        else:
            flash('Please connect a YouTube account first', 'error')
            return redirect(url_for('accounts_list'))

    # Verify account exists and has credentials
    account = db.get_youtube_account(account_id)
    if not account:
        flash('YouTube account not found', 'error')
        return redirect(url_for('accounts_list'))

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
        args=(video_id, account_id, title, description, tags, privacy)
    )
    thread.daemon = True
    thread.start()

    flash('YouTube upload started! This may take a few minutes.', 'success')
    return redirect(url_for('video_detail', video_id=video_id))


# ============== Content Types ==============

@app.route('/content-types')
def content_types_list():
    """List all content types."""
    content_types = db.get_all_content_types()
    return render_template('content_types.html', content_types=content_types)


@app.route('/content-types/new', methods=['GET', 'POST'])
def content_type_new():
    """Create a new content type."""
    if request.method == 'POST':
        try:
            content_type_id = db.create_content_type(
                slug=request.form.get('slug', '').strip().lower(),
                name=request.form.get('name', '').strip(),
                theme_prompt=request.form.get('theme_prompt', '').strip(),
                image_style_prompt=request.form.get('image_style_prompt', '').strip(),
                script_prompt=request.form.get('script_prompt', '').strip(),
                description=request.form.get('description', '').strip(),
                icon=request.form.get('icon', ''),
                voice_id=request.form.get('voice_id', config.DEFAULT_VOICE),
                voice_style=request.form.get('voice_style', '').strip(),
                music_folder=request.form.get('music_folder', 'general'),
                default_duration=request.form.get('default_duration', 14, type=int),
                is_active='is_active' in request.form
            )
            flash('Content type created successfully!', 'success')
            return redirect(url_for('content_types_list'))
        except Exception as e:
            flash(f'Error creating content type: {str(e)}', 'error')

    return render_template(
        'content_type_edit.html',
        content_type=None,
        voices=get_available_voices(),
        music_folders=list_music_folders()
    )


@app.route('/content-types/<int:content_type_id>/edit', methods=['GET', 'POST'])
def content_type_edit(content_type_id):
    """Edit an existing content type."""
    content_type = db.get_content_type(content_type_id)
    if not content_type:
        flash('Content type not found', 'error')
        return redirect(url_for('content_types_list'))

    if request.method == 'POST':
        try:
            db.update_content_type(
                content_type_id,
                slug=request.form.get('slug', '').strip().lower(),
                name=request.form.get('name', '').strip(),
                theme_prompt=request.form.get('theme_prompt', '').strip(),
                image_style_prompt=request.form.get('image_style_prompt', '').strip(),
                script_prompt=request.form.get('script_prompt', '').strip(),
                description=request.form.get('description', '').strip(),
                icon=request.form.get('icon', ''),
                voice_id=request.form.get('voice_id', config.DEFAULT_VOICE),
                voice_style=request.form.get('voice_style', '').strip(),
                music_folder=request.form.get('music_folder', 'general'),
                default_duration=request.form.get('default_duration', 14, type=int),
                is_active='is_active' in request.form
            )
            flash('Content type updated successfully!', 'success')
            return redirect(url_for('content_types_list'))
        except Exception as e:
            flash(f'Error updating content type: {str(e)}', 'error')

    return render_template(
        'content_type_edit.html',
        content_type=content_type,
        voices=get_available_voices(),
        music_folders=list_music_folders()
    )


@app.route('/content-types/<int:content_type_id>/toggle', methods=['POST'])
def content_type_toggle(content_type_id):
    """Toggle content type active status."""
    new_status = db.toggle_content_type(content_type_id)
    status_text = 'activated' if new_status else 'deactivated'
    flash(f'Content type {status_text}', 'success')
    return redirect(url_for('content_types_list'))


@app.route('/content-types/<int:content_type_id>/delete', methods=['POST'])
def content_type_delete(content_type_id):
    """Delete a content type."""
    if db.delete_content_type(content_type_id):
        flash('Content type deleted', 'success')
    else:
        flash('Cannot delete: content type has videos', 'error')
    return redirect(url_for('content_types_list'))


# ============== YouTube Accounts ==============

@app.route('/accounts')
def accounts_list():
    """List all YouTube accounts."""
    accounts = db.get_all_youtube_accounts()
    return render_template(
        'accounts.html',
        accounts=accounts,
        client_secrets_exists=os.path.exists(config.GOOGLE_CLIENT_SECRETS_FILE)
    )


@app.route('/accounts/<int:account_id>/default', methods=['POST'])
def account_set_default(account_id):
    """Set an account as default."""
    db.set_default_youtube_account(account_id)
    flash('Default account updated', 'success')
    return redirect(url_for('accounts_list'))


@app.route('/accounts/<int:account_id>/delete', methods=['POST'])
def account_delete(account_id):
    """Delete a YouTube account."""
    if db.delete_youtube_account(account_id):
        flash('Account removed', 'success')
    else:
        flash('Error removing account', 'error')
    return redirect(url_for('accounts_list'))


# ============== YouTube OAuth ==============

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

        # Get credentials and create account
        creds = flow.credentials
        account_id = youtube.create_account_from_oauth(creds)

        if account_id:
            flash('YouTube account connected successfully!', 'success')
        else:
            flash('Error creating account', 'error')

    except Exception as e:
        flash(f'Error connecting YouTube: {str(e)}', 'error')

    return redirect(url_for('accounts_list'))


@app.route('/youtube/disconnect', methods=['POST'])
def youtube_disconnect():
    """Disconnect all YouTube accounts (legacy route)."""
    # Redirect to accounts page for proper management
    return redirect(url_for('accounts_list'))


# ============== Settings ==============

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

    # Get YouTube accounts
    youtube_accounts = db.get_all_youtube_accounts()

    # Get music folder info
    music_folders = {}
    for folder in list_music_folders():
        files = list_music_files(folder)
        music_folders[folder] = len(files)

    # Count content types
    content_types_count = len(db.get_all_content_types())

    return render_template(
        'settings.html',
        anthropic_key=config.ANTHROPIC_API_KEY,
        hf_token=config.HF_API_TOKEN,
        default_voice=config.DEFAULT_VOICE,
        available_voices=get_available_voices(),
        youtube_accounts=youtube_accounts,
        music_folders=music_folders,
        content_types_count=content_types_count,
        client_secrets_exists=os.path.exists(config.GOOGLE_CLIENT_SECRETS_FILE)
    )


# ============== API Endpoints ==============

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


@app.route('/api/content-types')
def api_content_types():
    """API endpoint to get all content types as JSON."""
    content_types = db.get_all_content_types()
    return jsonify(content_types)


@app.route('/api/youtube/status')
def youtube_status():
    """Return YouTube auth status as JSON."""
    accounts = db.get_all_youtube_accounts()
    return jsonify({
        'authenticated': len(accounts) > 0,
        'accounts': accounts
    })


# ============== Template Filters ==============

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


if __name__ == '__main__':
    # Initialize database
    db.init_db()

    # Seed default content types if needed
    db.seed_content_types()

    # Ensure credentials directory exists
    os.makedirs(config.CREDENTIALS_DIR, exist_ok=True)

    # Allow OAuth over HTTP for local development
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)
