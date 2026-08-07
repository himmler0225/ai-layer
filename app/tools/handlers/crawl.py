from typing import Any

import app.config.settings as settings
from app.clients import data_miner
from app.services.url_extractor import extract_id_from_url as _url_extract


def _parse_video_ids(raw) -> list[str]:
    """Normalize a comma-separated string or iterable of video IDs into a clean list.

    Args:
        raw: Either a comma-separated string of IDs or an iterable of ID-like values.

    Returns:
        A list of trimmed, non-empty ID strings.
    """
    if isinstance(raw, str):
        return [v.strip() for v in raw.split(",") if v.strip()]
    return [str(v).strip() for v in raw if str(v).strip()]


async def youtube_search(inp: dict) -> Any:
    """Tool handler: search YouTube videos by keyword.

    Args:
        inp: Tool input with "keyword" and optional "max_results", "sort".

    Returns:
        The result of `data_miner.search_youtube`.
    """
    return await data_miner.search_youtube(
        query=inp["keyword"], max_results=inp.get("max_results", 5), sort=inp.get("sort", "relevance")
    )


async def youtube_get_by_topic(inp: dict) -> Any:
    """Tool handler: get YouTube videos for a topic (e.g. music, gaming).

    Args:
        inp: Tool input with "topic" and optional "max_results".

    Returns:
        The result of `data_miner.get_by_topic`.
    """
    return await data_miner.get_by_topic(topic=inp["topic"], max_results=inp.get("max_results", 20))


async def youtube_get_shorts(inp: dict) -> Any:
    """Tool handler: get trending YouTube Shorts.

    Args:
        inp: Tool input with optional "max_results".

    Returns:
        The result of `data_miner.get_shorts`.
    """
    return await data_miner.get_shorts(max_results=inp.get("max_results", 20))


async def youtube_get_live(inp: dict) -> Any:
    """Tool handler: get currently live YouTube streams, optionally filtered by keyword.

    Args:
        inp: Tool input with optional "query" and "max_results".

    Returns:
        The result of `data_miner.get_live`.
    """
    return await data_miner.get_live(query=inp.get("query", ""), max_results=inp.get("max_results", 20))


async def youtube_get_by_region(inp: dict) -> Any:
    """Tool handler: get popular YouTube videos for a specific region and language.

    Args:
        inp: Tool input with "gl" (region), "query", and optional "hl" (language), "max_results".

    Returns:
        The result of `data_miner.get_by_region`.
    """
    return await data_miner.get_by_region(
        gl=inp["gl"], hl=inp.get("hl", "vi"), query=inp["query"], max_results=inp.get("max_results", 20)
    )


async def youtube_get_detail(inp: dict) -> Any:
    """Tool handler: get details for a single YouTube video.

    Args:
        inp: Tool input with "video_id".

    Returns:
        The result of `data_miner.get_video_detail`.
    """
    return await data_miner.get_video_detail(inp["video_id"])


async def youtube_get_comments(inp: dict) -> Any:
    """Tool handler: get comments for a single YouTube video.

    Args:
        inp: Tool input with "video_id" and optional "max_comments", "sort".

    Returns:
        The result of `data_miner.get_video_comments`.
    """
    return await data_miner.get_video_comments(
        video_id=inp["video_id"],
        max_comments=inp.get("max_comments", settings.AGENT_MAX_COMMENTS),
        sort=inp.get("sort", "top"),
    )


async def youtube_get_comments_batch(inp: dict) -> Any:
    """Tool handler: get comments for up to 8 YouTube videos in a single batch call.

    Args:
        inp: Tool input with "video_ids" (string or list, truncated to 8)
            and optional "max_per_video", "sort" (restricted to "top"/"newest").

    Returns:
        The result of `data_miner.get_video_comments_batch`.
    """
    ids = _parse_video_ids(inp.get("video_ids", []))[:8]
    sort = inp.get("sort", "top")
    if sort not in ("top", "newest"):
        sort = "top"
    return await data_miner.get_video_comments_batch(
        video_ids=ids, max_per_video=inp.get("max_per_video", settings.AGENT_MAX_COMMENTS), sort=sort
    )


async def youtube_get_transcript(inp: dict) -> Any:
    """Tool handler: get the transcript/captions for a single YouTube video.

    Args:
        inp: Tool input with "video_id".

    Returns:
        The result of `data_miner.get_video_transcript`.
    """
    return await data_miner.get_video_transcript(inp["video_id"])


async def youtube_get_transcript_batch(inp: dict) -> Any:
    """Tool handler: get transcripts for up to 8 YouTube videos in a single batch call.

    Args:
        inp: Tool input with "video_ids" (string or list, truncated to 8).

    Returns:
        The result of `data_miner.get_video_transcript_batch`.
    """
    return await data_miner.get_video_transcript_batch(_parse_video_ids(inp.get("video_ids", []))[:8])


async def youtube_get_channel_info(inp: dict) -> Any:
    """Tool handler: get info about a YouTube channel.

    Args:
        inp: Tool input with "channel_id".

    Returns:
        The result of `data_miner.get_channel_info`.
    """
    return await data_miner.get_channel_info(inp["channel_id"])


async def youtube_get_channel_videos(inp: dict) -> Any:
    """Tool handler: get the latest videos from a YouTube channel.

    Args:
        inp: Tool input with "channel_id" and optional "max_results".

    Returns:
        The result of `data_miner.get_channel_videos`.
    """
    return await data_miner.get_channel_videos(channel_id=inp["channel_id"], max_results=inp.get("max_results", 30))


async def youtube_get_channel_playlists(inp: dict) -> Any:
    """Tool handler: get the playlists of a YouTube channel.

    Args:
        inp: Tool input with "channel_id".

    Returns:
        The result of `data_miner.get_channel_playlists`.
    """
    return await data_miner.get_channel_playlists(inp["channel_id"])


async def youtube_get_playlist_videos(inp: dict) -> Any:
    """Tool handler: get the videos in a YouTube playlist.

    Args:
        inp: Tool input with "playlist_id" and optional "max_results".

    Returns:
        The result of `data_miner.get_playlist_videos`.
    """
    return await data_miner.get_playlist_videos(playlist_id=inp["playlist_id"], max_results=inp.get("max_results", 30))


async def tiktok_search(inp: dict) -> Any:
    """Tool handler: search TikTok videos by keyword.

    Args:
        inp: Tool input with "keyword" and optional "cursor", "sort_by", "date_posted", "region".

    Returns:
        The result of `data_miner.tiktok_search`.
    """
    return await data_miner.tiktok_search(
        keyword=inp["keyword"],
        cursor=inp.get("cursor", 0),
        sort_by=inp.get("sort_by"),
        date_posted=inp.get("date_posted"),
        region=inp.get("region"),
    )


async def tiktok_video_info(inp: dict) -> Any:
    """Tool handler: get info for a single TikTok video by URL.

    Args:
        inp: Tool input with "url".

    Returns:
        The result of `data_miner.tiktok_video_info`.
    """
    return await data_miner.tiktok_video_info(url=inp["url"])


async def tiktok_comments(inp: dict) -> Any:
    """Tool handler: get comments for a TikTok video.

    Args:
        inp: Tool input with "aweme_id" and optional "cursor", "count".

    Returns:
        The result of `data_miner.tiktok_comments`.
    """
    return await data_miner.tiktok_comments(
        aweme_id=inp["aweme_id"], cursor=inp.get("cursor", 0), count=inp.get("count", 20)
    )


async def tiktok_profile(inp: dict) -> Any:
    """Tool handler: get a TikTok profile by handle.

    Args:
        inp: Tool input with "handle".

    Returns:
        The result of `data_miner.tiktok_profile`.
    """
    return await data_miner.tiktok_profile(inp["handle"])


async def tiktok_transcript(inp: dict) -> Any:
    """Tool handler: get the transcript for a TikTok video.

    Args:
        inp: Tool input with "aweme_id".

    Returns:
        The result of `data_miner.tiktok_transcript`.
    """
    return await data_miner.tiktok_transcript(aweme_id=inp["aweme_id"])


async def web_search(inp: dict) -> Any:
    """Tool handler: perform a general web search.

    Args:
        inp: Tool input with "query" and optional "max_results".

    Returns:
        The result of `data_miner.search_web`.
    """
    return await data_miner.search_web(query=inp["query"], max_results=inp.get("max_results", 5))


async def extract_id_from_url(inp: dict) -> Any:
    """Tool handler: extract the platform and video/content ID from a pasted URL.

    Args:
        inp: Tool input with "url".

    Returns:
        The result of `_url_extract` (platform-specific ID info).
    """
    return _url_extract(url=inp["url"])


async def movie_search(inp: dict) -> Any:
    """Tool handler: search movies by keyword.

    Args:
        inp: Tool input with "keyword" and optional "provider", "page", "limit".

    Returns:
        The result of `data_miner.movie_search`.
    """
    return await data_miner.movie_search(
        inp["keyword"], provider=inp.get("provider"), page=inp.get("page", 1), limit=inp.get("limit", 10)
    )


async def movie_get_detail(inp: dict) -> Any:
    """Tool handler: get movie details by slug.

    Args:
        inp: Tool input with "slug" and optional "provider".

    Returns:
        The result of `data_miner.movie_get_detail`.
    """
    return await data_miner.movie_get_detail(inp["slug"], provider=inp.get("provider"))


async def movie_list_new(inp: dict) -> Any:
    """Tool handler: get the list of newly updated movies.

    Args:
        inp: Tool input with optional "provider", "page".

    Returns:
        The result of `data_miner.movie_list_new`.
    """
    return await data_miner.movie_list_new(provider=inp.get("provider"), page=inp.get("page", 1))


async def movie_list_by_type(inp: dict) -> Any:
    """Tool handler: get movies filtered by type (e.g. phim-bo, phim-le, tv-shows).

    Args:
        inp: Tool input with "type" and optional "provider", "page", "limit",
            "category", "country", "year", "sort_lang", "sort_field", "sort_type".

    Returns:
        The result of `data_miner.movie_list_by_type`.
    """
    return await data_miner.movie_list_by_type(
        inp["type"],
        provider=inp.get("provider"),
        page=inp.get("page", 1),
        limit=inp.get("limit", 10),
        category=inp.get("category"),
        country=inp.get("country"),
        year=inp.get("year"),
        sort_lang=inp.get("sort_lang"),
        sort_field=inp.get("sort_field"),
        sort_type=inp.get("sort_type"),
    )


async def movie_list_by_genre(inp: dict) -> Any:
    """Tool handler: get movies filtered by genre slug.

    Args:
        inp: Tool input with "slug" and optional "provider", "page", "limit",
            "category", "country", "year", "sort_lang", "sort_field", "sort_type".

    Returns:
        The result of `data_miner.movie_list_by_genre`.
    """
    return await data_miner.movie_list_by_genre(
        inp["slug"],
        provider=inp.get("provider"),
        page=inp.get("page", 1),
        limit=inp.get("limit", 10),
        category=inp.get("category"),
        country=inp.get("country"),
        year=inp.get("year"),
        sort_lang=inp.get("sort_lang"),
        sort_field=inp.get("sort_field"),
        sort_type=inp.get("sort_type"),
    )


async def movie_list_by_country(inp: dict) -> Any:
    """Tool handler: get movies filtered by country slug.

    Args:
        inp: Tool input with "slug" and optional "provider", "page", "limit",
            "category", "country", "year", "sort_lang", "sort_field", "sort_type".

    Returns:
        The result of `data_miner.movie_list_by_country`.
    """
    return await data_miner.movie_list_by_country(
        inp["slug"],
        provider=inp.get("provider"),
        page=inp.get("page", 1),
        limit=inp.get("limit", 10),
        category=inp.get("category"),
        country=inp.get("country"),
        year=inp.get("year"),
        sort_lang=inp.get("sort_lang"),
        sort_field=inp.get("sort_field"),
        sort_type=inp.get("sort_type"),
    )


async def movie_list_by_year(inp: dict) -> Any:
    """Tool handler: get movies filtered by release year.

    Args:
        inp: Tool input with "year" and optional "provider", "page", "limit",
            "category", "country", "sort_lang", "sort_field", "sort_type".

    Returns:
        The result of `data_miner.movie_list_by_year`.
    """
    return await data_miner.movie_list_by_year(
        inp["year"],
        provider=inp.get("provider"),
        page=inp.get("page", 1),
        limit=inp.get("limit", 10),
        category=inp.get("category"),
        country=inp.get("country"),
        sort_lang=inp.get("sort_lang"),
        sort_field=inp.get("sort_field"),
        sort_type=inp.get("sort_type"),
    )


async def movie_get_metadata(inp: dict) -> Any:
    """Tool handler: get movie genre or country metadata lists.

    Args:
        inp: Tool input with "kind" ("genres" or "countries") and optional "provider".

    Returns:
        The result of `data_miner.movie_get_genres` when kind is "genres",
        otherwise `data_miner.movie_get_countries`.
    """
    provider = inp.get("provider")
    if inp["kind"] == "genres":
        return await data_miner.movie_get_genres(provider=provider)
    return await data_miner.movie_get_countries(provider=provider)


CRAWL_HANDLERS = {
    "youtube_search": youtube_search,
    "youtube_get_by_topic": youtube_get_by_topic,
    "youtube_get_shorts": youtube_get_shorts,
    "youtube_get_live": youtube_get_live,
    "youtube_get_by_region": youtube_get_by_region,
    "youtube_get_detail": youtube_get_detail,
    "youtube_get_comments": youtube_get_comments,
    "youtube_get_comments_batch": youtube_get_comments_batch,
    "youtube_get_transcript": youtube_get_transcript,
    "youtube_get_transcript_batch": youtube_get_transcript_batch,
    "youtube_get_channel_info": youtube_get_channel_info,
    "youtube_get_channel_videos": youtube_get_channel_videos,
    "youtube_get_channel_playlists": youtube_get_channel_playlists,
    "youtube_get_playlist_videos": youtube_get_playlist_videos,
    "tiktok_search": tiktok_search,
    "tiktok_video_info": tiktok_video_info,
    "tiktok_comments": tiktok_comments,
    "tiktok_profile": tiktok_profile,
    "tiktok_transcript": tiktok_transcript,
    "web_search": web_search,
    "extract_id_from_url": extract_id_from_url,
    "movie_search": movie_search,
    "movie_get_detail": movie_get_detail,
    "movie_list_new": movie_list_new,
    "movie_list_by_type": movie_list_by_type,
    "movie_list_by_genre": movie_list_by_genre,
    "movie_list_by_country": movie_list_by_country,
    "movie_list_by_year": movie_list_by_year,
    "movie_get_metadata": movie_get_metadata,
}
