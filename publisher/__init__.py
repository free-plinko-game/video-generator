"""YouTube publishing module for Content Factory."""

from .youtube import (
    is_authenticated,
    get_authenticated_service,
    upload_video,
    generate_video_metadata,
    get_channel_info,
    create_account_from_oauth,
    disconnect,
)

__all__ = [
    'is_authenticated',
    'get_authenticated_service',
    'upload_video',
    'generate_video_metadata',
    'get_channel_info',
    'create_account_from_oauth',
    'disconnect',
]
