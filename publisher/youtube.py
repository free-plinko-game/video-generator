"""YouTube API integration for uploading videos as Shorts."""

import os
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

import config


def is_authenticated() -> bool:
    """Check if YouTube credentials exist and are valid."""
    if not os.path.exists(config.YOUTUBE_CREDENTIALS_FILE):
        return False

    try:
        creds = _load_credentials()
        return creds is not None and creds.valid
    except Exception:
        return False


def _load_credentials() -> Optional[Credentials]:
    """Load credentials from file."""
    if not os.path.exists(config.YOUTUBE_CREDENTIALS_FILE):
        return None

    try:
        creds = Credentials.from_authorized_user_file(
            config.YOUTUBE_CREDENTIALS_FILE,
            config.YOUTUBE_SCOPES
        )

        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_credentials(creds)

        return creds
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


def _save_credentials(creds: Credentials) -> None:
    """Save credentials to file."""
    os.makedirs(os.path.dirname(config.YOUTUBE_CREDENTIALS_FILE), exist_ok=True)

    with open(config.YOUTUBE_CREDENTIALS_FILE, 'w') as f:
        f.write(creds.to_json())


def get_authenticated_service():
    """
    Get an authenticated YouTube API service.

    Returns:
        YouTube API service object

    Raises:
        ValueError: If not authenticated
    """
    creds = _load_credentials()

    if not creds or not creds.valid:
        raise ValueError("YouTube not authenticated. Please connect your account in Settings.")

    return build('youtube', 'v3', credentials=creds)


def run_oauth_flow(redirect_uri: str = None) -> str:
    """
    Start the OAuth flow for YouTube authentication.

    Args:
        redirect_uri: Optional redirect URI for web flow

    Returns:
        str: Authorization URL for the user to visit

    Raises:
        ValueError: If client secrets file not found
    """
    if not os.path.exists(config.GOOGLE_CLIENT_SECRETS_FILE):
        raise ValueError(
            "client_secrets.json not found. Please download it from Google Cloud Console "
            "and place it in the project root directory."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        config.GOOGLE_CLIENT_SECRETS_FILE,
        scopes=config.YOUTUBE_SCOPES,
        redirect_uri=redirect_uri
    )

    return flow


def complete_oauth_flow(flow, authorization_response: str) -> Credentials:
    """
    Complete the OAuth flow after user authorization.

    Args:
        flow: The OAuth flow object
        authorization_response: The full callback URL with code

    Returns:
        Credentials object
    """
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    _save_credentials(creds)
    return creds


def run_local_oauth_flow() -> bool:
    """
    Run OAuth flow locally (opens browser).
    Use this for command-line setup.

    Returns:
        bool: True if successful
    """
    if not os.path.exists(config.GOOGLE_CLIENT_SECRETS_FILE):
        raise ValueError(
            "client_secrets.json not found. Please download it from Google Cloud Console."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        config.GOOGLE_CLIENT_SECRETS_FILE,
        scopes=config.YOUTUBE_SCOPES
    )

    creds = flow.run_local_server(port=8090)
    _save_credentials(creds)
    return True


def get_channel_info() -> Optional[Dict[str, Any]]:
    """
    Get information about the authenticated YouTube channel.

    Returns:
        Dict with channel info or None if not authenticated
    """
    try:
        youtube = get_authenticated_service()
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


def disconnect() -> bool:
    """
    Disconnect YouTube account by removing credentials.

    Returns:
        bool: True if successful
    """
    try:
        if os.path.exists(config.YOUTUBE_CREDENTIALS_FILE):
            os.remove(config.YOUTUBE_CREDENTIALS_FILE)
        return True
    except Exception as e:
        print(f"Error disconnecting: {e}")
        return False


def upload_video(
    video_path: str,
    title: str,
    description: str,
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

    youtube = get_authenticated_service()

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


def generate_video_metadata(video_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate YouTube title and description using Claude.

    Args:
        video_record: Video database record

    Returns:
        Dict with 'title', 'description', 'tags'
    """
    if not config.ANTHROPIC_API_KEY:
        # Return default metadata if no API key
        return {
            'title': f"Liminal Space: {video_record.get('location', 'Unknown')} #{video_record.get('id', '')}",
            'description': f"{video_record.get('voiceover_script', '')}\n\n#shorts #liminal #liminalspace",
            'tags': config.YOUTUBE_DEFAULT_TAGS
        }

    prompt = f"""Generate YouTube Shorts metadata for a liminal space video.

Video concept:
- Location: {video_record.get('location', 'Unknown location')}
- Time: {video_record.get('time_of_day', 'Late night')}
- Mood: {video_record.get('mood', 'Eerie')}
- Voiceover: {video_record.get('voiceover_script', '')}

Return JSON only, no other text:
{{
  "title": "Engaging title, under 70 chars, include 'liminal' or mysterious hook",
  "description": "2-3 sentences, atmospheric, include hashtags at end. Add #shorts",
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
            metadata['title'] = f"Liminal Space: {video_record.get('location', 'Unknown')}"
        if 'description' not in metadata:
            metadata['description'] = f"{video_record.get('voiceover_script', '')}\n\n#shorts #liminal"
        if 'tags' not in metadata:
            metadata['tags'] = config.YOUTUBE_DEFAULT_TAGS

        return metadata

    except Exception as e:
        print(f"Error generating metadata: {e}")
        return {
            'title': f"Liminal Space: {video_record.get('location', 'Unknown')}",
            'description': f"{video_record.get('voiceover_script', '')}\n\n#shorts #liminal #liminalspace",
            'tags': config.YOUTUBE_DEFAULT_TAGS
        }


def delete_video(video_id: str) -> bool:
    """
    Delete a video from YouTube.

    Args:
        video_id: YouTube video ID

    Returns:
        bool: True if successful
    """
    try:
        youtube = get_authenticated_service()
        youtube.videos().delete(id=video_id).execute()
        return True
    except HttpError as e:
        print(f"Error deleting video: {e}")
        return False


if __name__ == "__main__":
    # Command-line setup helper
    print("YouTube OAuth Setup")
    print("=" * 40)

    if is_authenticated():
        print("Already authenticated!")
        channel = get_channel_info()
        if channel:
            print(f"Connected as: {channel['title']}")
    else:
        print("Starting OAuth flow...")
        try:
            run_local_oauth_flow()
            print("Successfully authenticated!")
            channel = get_channel_info()
            if channel:
                print(f"Connected as: {channel['title']}")
        except Exception as e:
            print(f"Error: {e}")
