from typing import Any

import app.config.settings as settings
from app.clients import data_miner
from app.services.url_extractor import extract_id_from_url as _url_extract


def _parse_video_ids(raw) -> list[str]:
    if isinstance(raw, str):
        return [v.strip() for v in raw.split(",") if v.strip()]
    return [str(v).strip() for v in raw if str(v).strip()]


async def youtube_search(inp: dict) -> Any:
    return await data_miner.search_youtube(
        query=inp["keyword"], max_results=inp.get("max_results", 5), sort=inp.get("sort", "relevance")
    )


async def youtube_get_by_topic(inp: dict) -> Any:
    return await data_miner.get_by_topic(topic=inp["topic"], max_results=inp.get("max_results", 20))


async def youtube_get_shorts(inp: dict) -> Any:
    return await data_miner.get_shorts(max_results=inp.get("max_results", 20))


async def youtube_get_live(inp: dict) -> Any:
    return await data_miner.get_live(query=inp.get("query", ""), max_results=inp.get("max_results", 20))


async def youtube_get_by_region(inp: dict) -> Any:
    return await data_miner.get_by_region(
        gl=inp["gl"], hl=inp.get("hl", "vi"), query=inp["query"], max_results=inp.get("max_results", 20)
    )


async def youtube_get_detail(inp: dict) -> Any:
    return await data_miner.get_video_detail(inp["video_id"])


async def youtube_get_comments(inp: dict) -> Any:
    return await data_miner.get_video_comments(
        video_id=inp["video_id"],
        max_comments=inp.get("max_comments", settings.AGENT_MAX_COMMENTS),
        sort=inp.get("sort", "top"),
    )


async def youtube_get_comments_batch(inp: dict) -> Any:
    ids = _parse_video_ids(inp.get("video_ids", []))[:8]
    sort = inp.get("sort", "top")
    if sort not in ("top", "newest"):
        sort = "top"
    return await data_miner.get_video_comments_batch(
        video_ids=ids, max_per_video=inp.get("max_per_video", settings.AGENT_MAX_COMMENTS), sort=sort
    )


async def youtube_get_transcript(inp: dict) -> Any:
    return await data_miner.get_video_transcript(inp["video_id"])


async def youtube_get_transcript_batch(inp: dict) -> Any:
    return await data_miner.get_video_transcript_batch(_parse_video_ids(inp.get("video_ids", []))[:8])


async def youtube_get_channel_info(inp: dict) -> Any:
    return await data_miner.get_channel_info(inp["channel_id"])


async def youtube_get_channel_videos(inp: dict) -> Any:
    return await data_miner.get_channel_videos(channel_id=inp["channel_id"], max_results=inp.get("max_results", 30))


async def youtube_get_channel_playlists(inp: dict) -> Any:
    return await data_miner.get_channel_playlists(inp["channel_id"])


async def youtube_get_playlist_videos(inp: dict) -> Any:
    return await data_miner.get_playlist_videos(playlist_id=inp["playlist_id"], max_results=inp.get("max_results", 30))


async def tiktok_search(inp: dict) -> Any:
    return await data_miner.tiktok_search(
        keyword=inp["keyword"],
        cursor=inp.get("cursor", 0),
        sort_by=inp.get("sort_by"),
        date_posted=inp.get("date_posted"),
        region=inp.get("region"),
    )


async def tiktok_video_info(inp: dict) -> Any:
    return await data_miner.tiktok_video_info(url=inp["url"])


async def tiktok_comments(inp: dict) -> Any:
    return await data_miner.tiktok_comments(
        aweme_id=inp["aweme_id"], cursor=inp.get("cursor", 0), count=inp.get("count", 20)
    )


async def tiktok_profile(inp: dict) -> Any:
    return await data_miner.tiktok_profile(inp["handle"])


async def tiktok_transcript(inp: dict) -> Any:
    return await data_miner.tiktok_transcript(aweme_id=inp["aweme_id"])


async def extract_id_from_url(inp: dict) -> Any:
    return _url_extract(url=inp["url"])


async def movie_search(inp: dict) -> Any:
    return await data_miner.movie_search(
        inp["keyword"], provider=inp.get("provider"), page=inp.get("page", 1), limit=inp.get("limit", 10)
    )


async def movie_get_detail(inp: dict) -> Any:
    return await data_miner.movie_get_detail(inp["slug"], provider=inp.get("provider"))


async def movie_list_new(inp: dict) -> Any:
    return await data_miner.movie_list_new(provider=inp.get("provider"), page=inp.get("page", 1))


async def movie_list_by_type(inp: dict) -> Any:
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
