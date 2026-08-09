"""Data-miner HTTP client — split by domain (youtube / tiktok). Movie catalog
lives in app.clients.movie_aggregator (calls movie-aggregator-api directly)."""

from app.clients.data_miner._http import close_client
from app.clients.data_miner.tiktok import (
    tiktok_comments,
    tiktok_profile,
    tiktok_search,
    tiktok_transcript,
    tiktok_video_info,
)
from app.clients.data_miner.web import search_web
from app.clients.data_miner.youtube import (
    get_by_region,
    get_by_topic,
    get_channel_info,
    get_channel_playlists,
    get_channel_videos,
    get_live,
    get_playlist_videos,
    get_shorts,
    get_trending,
    get_video_comments,
    get_video_comments_batch,
    get_video_detail,
    get_video_transcript,
    get_video_transcript_batch,
    search_youtube,
)

__all__ = [
    "close_client",
    "get_by_region",
    "get_by_topic",
    "get_channel_info",
    "get_channel_playlists",
    "get_channel_videos",
    "get_live",
    "get_playlist_videos",
    "get_shorts",
    "get_trending",
    "get_video_comments",
    "get_video_comments_batch",
    "get_video_detail",
    "get_video_transcript",
    "get_video_transcript_batch",
    "search_web",
    "search_youtube",
    "tiktok_comments",
    "tiktok_profile",
    "tiktok_search",
    "tiktok_transcript",
    "tiktok_video_info",
]
