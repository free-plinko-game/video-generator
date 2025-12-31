"""YouTube API integration for uploading videos - multi-account support."""

import os
import sys
import json
import httplib2
from typing import Optional, Dict, Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import anthropic

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import db


def get_credentials_path(account_id: int) -> str:
    """Get the credentials file path for an account."""
    return os.path.join(config.CREDENTIALS_DIR, f"account_{account_id}.json")


def is_authenticated(account_id: int = None) -> bool:
    """
    Check if YouTube credentials exist and are valid.

    Args:
        account_id: Specific account ID, or None to check for any account
    """
    if account_id:
        account = db.get_youtube_account(account_id)
        if not account:
            return False
        creds_path = account.get('credentials_path')
        if not creds_path or not os.path.exists(creds_path):
            return False
        try:
            creds = _load_credentials(creds_path)
            return creds is not None and creds.valid
        except Exception:
            return False
    else:
        # Check if any account is authenticated
        accounts = db.get_all_youtube_accounts()
        return len(accounts) > 0


def _load_credentials(creds_path: str) -> Optional[Credentials]:
    """Load credentials from file."""
    if not os.path.exists(creds_path):
        return None

    try:
        creds = Credentials.from_authorized_user_file(
            creds_path,
            config.YOUTUBE_SCOPES
        )

        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_credentials(creds, creds_path)

        return creds
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


def _save_credentials(creds: Credentials, creds_path: str) -> None:
    """Save credentials to file."""
    os.makedirs(os.path.dirname(creds_path), exist_ok=True)

    with open(creds_path, 'w') as f:
        f.write(creds.to_json())


def get_authenticated_service(account_id: int = None):
    """
    Get an authenticated YouTube API service.

    Args:
        account_id: Account ID to use, or None for default account

    Returns:
        YouTube API service object

    Raises:
        ValueError: If not authenticated
    """
    if account_id is None:
        account = db.get_default_youtube_account()
    else:
        account = db.get_youtube_account(account_id)

    if not account:
        raise ValueError("No YouTube account found. Please connect an account.")

    creds_path = account.get('credentials_path')
    if not creds_path or not os.path.exists(creds_path):
        raise ValueError("YouTube credentials not found. Please reconnect the account.")

    creds = _load_credentials(creds_path)

    if not creds or not creds.valid:
        raise ValueError("YouTube credentials invalid. Please reconnect the account.")

    return build('youtube', 'v3', credentials=creds)


def get_channel_info(account_id: int = None) -> Optional[Dict[str, Any]]:
    """
    Get information about a YouTube channel.

    Args:
        account_id: Account ID to check, or None for default

    Returns:
        Dict with channel info or None if not authenticated
    """
    try:
        youtube = get_authenticated_service(account_id)
        response = youtube.channels().list(
            part='snippet,statistics',
            mine=True
        ).execute()

        if response.get('items'):
            channel = response['items'][0]
            return {
                'id': channel['id'],
                'title': channel['snippet']['title'],
                'description': channel['snippet'].get('description', ''),
                'thumbnail': channel['snippet']['thumbnails'].get('default', {}).get('url'),
                'subscriber_count': channel['statistics'].get('subscriberCount', '0'),
                'video_count': channel['statistics'].get('videoCount', '0'),
            }
        return None
    except Exception as e:
        print(f"Error getting channel info: {e}")
        return None


def create_account_from_oauth(creds: Credentials, account_name: str = None) -> int:
    """
    Create a new YouTube account record from OAuth credentials.

    Args:
        creds: OAuth credentials
        account_name: Optional name for the account

    Returns:
        Account ID
    """
    # Find next available account ID
    accounts = db.get_all_youtube_accounts()
    next_id = max([a['id'] for a in accounts], default=0) + 1

    # Save credentials to file
    creds_path = get_credentials_path(next_id)
    _save_credentials(creds, creds_path)

    # Get channel info
    youtube = build('youtube', 'v3', credentials=creds)
    response = youtube.channels().list(part='snippet', mine=True).execute()

    channel_id = None
    channel_name = None
    if response.get('items'):
        channel = response['items'][0]
        channel_id = channel['id']
        channel_name = channel['snippet']['title']

    if not account_name:
        account_name = channel_name or f"Account {next_id}"

    # Create database record
    account_id = db.create_youtube_account(
        name=account_name,
        credentials_path=creds_path,
        channel_id=channel_id,
        channel_name=channel_name
    )

    return account_id


def disconnect(account_id: int) -> bool:
    """
    Disconnect a YouTube account.

    Args:
        account_id: Account ID to disconnect

    Returns:
        bool: True if successful
    """
    return db.delete_youtube_account(account_id)


def upload_video(
    video_path: str,
    title: str,
    description: str,
    account_id: int = None,
    tags: list = None,
    privacy: str = None,
    category: str = None
) -> Dict[str, str]:
    """
    Upload a video to YouTube.

    Args:
        video_path: Path to the video file
        title: Video title
        description: Video description
        account_id: Account to upload to (uses default if None)
        tags: List of tags
        privacy: Privacy status ('public', 'private', 'unlisted')
        category: YouTube category ID

    Returns:
        Dict with 'id' and 'url' of the uploaded video

    Raises:
        ValueError: If not authenticated or video file not found
        HttpError: If upload fails
    """
    if not os.path.exists(video_path):
        raise ValueError(f"Video file not found: {video_path}")

    if tags is None:
        tags = config.YOUTUBE_DEFAULT_TAGS
    if privacy is None:
        privacy = config.YOUTUBE_DEFAULT_PRIVACY
    if category is None:
        category = config.YOUTUBE_DEFAULT_CATEGORY

    youtube = get_authenticated_service(account_id)

    # Prepare video metadata
    body = {
        'snippet': {
            'title': title[:100],  # YouTube title limit
            'description': description[:5000],  # YouTube description limit
            'tags': tags[:500] if tags else [],  # Limit tags
            'categoryId': category,
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False,
        }
    }

    # Create media upload object with resumable upload
    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        resumable=True,
        chunksize=1024 * 1024  # 1MB chunks
    )

    # Execute upload
    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response['id']
    video_url = f"https://youtube.com/shorts/{video_id}"

    return {
        'id': video_id,
        'url': video_url
    }


def generate_video_metadata(video_record: Dict[str, Any], content_type: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generate YouTube title and description using Claude.

    Args:
        video_record: Video database record
        content_type: Optional content type for context

    Returns:
        Dict with 'title', 'description', 'tags'
    """
    # Build context from video record
    theme_data = video_record.get('theme_data')
    if theme_data and isinstance(theme_data, str):
        try:
            theme_data = json.loads(theme_data)
        except:
            theme_data = {}

    content_type_name = video_record.get('content_type_name', 'Video')

    # Build a description of the video content
    content_desc = ""
    if theme_data:
        content_desc = json.dumps(theme_data, indent=2)
    else:
        content_desc = f"""
Location: {video_record.get('location', 'Unknown')}
Time: {video_record.get('time_of_day', 'Unknown')}
Mood: {video_record.get('mood', 'Unknown')}
Voiceover: {video_record.get('voiceover_script', '')}
"""

    if not config.ANTHROPIC_API_KEY:
        # Return default metadata if no API key
        return {
            'title': f"{content_type_name}: #{video_record.get('id', '')}",
            'description': f"{video_record.get('voiceover_script', '')}\n\n#shorts",
            'tags': config.YOUTUBE_DEFAULT_TAGS
        }

    prompt = f"""Generate YouTube Shorts metadata for this video.

Content Type: {content_type_name}

Video concept:
{content_desc}

Screen text: {video_record.get('screen_text', '')}

Return JSON only, no other text:
{{
  "title": "Engaging title, under 70 chars, intriguing hook",
  "description": "2-3 sentences describing the video, include relevant hashtags at end. Always include #shorts",
  "tags": ["array", "of", "relevant", "tags", "max 10"]
}}

Make it intriguing and clickable without being clickbait."""

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()

        # Handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        metadata = json.loads(response_text)

        # Ensure required fields
        if 'title' not in metadata:
            metadata['title'] = f"{content_type_name} #{video_record.get('id', '')}"
        if 'description' not in metadata:
            metadata['description'] = f"{video_record.get('voiceover_script', '')}\n\n#shorts"
        if 'tags' not in metadata:
            metadata['tags'] = config.YOUTUBE_DEFAULT_TAGS

        return metadata

    except Exception as e:
        print(f"Error generating metadata: {e}")
        return {
            'title': f"{content_type_name} #{video_record.get('id', '')}",
            'description': f"{video_record.get('voiceover_script', '')}\n\n#shorts",
            'tags': config.YOUTUBE_DEFAULT_TAGS
        }


def delete_video(video_id: str, account_id: int = None) -> bool:
    """
    Delete a video from YouTube.

    Args:
        video_id: YouTube video ID
        account_id: Account that owns the video

    Returns:
        bool: True if successful
    """
    try:
        youtube = get_authenticated_service(account_id)
        youtube.videos().delete(id=video_id).execute()
        return True
    except HttpError as e:
        print(f"Error deleting video: {e}")
        return False


if __name__ == "__main__":
    # Command-line helper
    print("YouTube Multi-Account Manager")
    print("=" * 40)

    accounts = db.get_all_youtube_accounts()
    if accounts:
        print(f"Connected accounts: {len(accounts)}")
        for acc in accounts:
            default = " (default)" if acc.get('is_default') else ""
            print(f"  - {acc['name']}: {acc.get('channel_name', 'Unknown')}{default}")
    else:
        print("No accounts connected yet.")
