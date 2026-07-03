from typing import Any

from app.clients import config as dm_config
from app.clients.data_miner._http import get as _get


def _movie_provider(provider: str | None = None) -> str:
    return (provider or dm_config.movie_default_provider()).strip().lower()


def _movie_filters(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None and value != ""}


def _list_params(
    provider: str | None,
    page: int,
    limit: int,
    *,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": _movie_provider(provider),
        "page": page,
        "limit": limit,
        **_movie_filters(
            category=category,
            country=country,
            year=year,
            sort_lang=sort_lang,
            sort_field=sort_field,
            sort_type=sort_type,
        ),
    }


async def movie_search(
    keyword: str,
    provider: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> dict:
    return await _get(
        "/api/movies/search",
        {
            "provider": _movie_provider(provider),
            "keyword": keyword,
            "page": page,
            "limit": limit,
        },
    )


async def movie_get_detail(slug: str, provider: str | None = None) -> dict:
    return await _get(f"/api/movies/{slug}", {"provider": _movie_provider(provider)})


async def movie_list_new(provider: str | None = None, page: int = 1) -> dict:
    return await _get("/api/movies/new", {"provider": _movie_provider(provider), "page": page})


async def movie_list_by_type(
    movie_type: str,
    provider: str | None = None,
    page: int = 1,
    limit: int = 10,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict:
    return await _get(
        f"/api/movies/types/{movie_type}",
        _list_params(
            provider,
            page,
            limit,
            category=category,
            country=country,
            year=year,
            sort_lang=sort_lang,
            sort_field=sort_field,
            sort_type=sort_type,
        ),
    )


async def movie_list_by_genre(
    slug: str,
    provider: str | None = None,
    page: int = 1,
    limit: int = 10,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict:
    return await _get(
        f"/api/movies/genres/{slug}",
        _list_params(
            provider,
            page,
            limit,
            category=category,
            country=country,
            year=year,
            sort_lang=sort_lang,
            sort_field=sort_field,
            sort_type=sort_type,
        ),
    )


async def movie_list_by_country(
    slug: str,
    provider: str | None = None,
    page: int = 1,
    limit: int = 10,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict:
    return await _get(
        f"/api/movies/countries/{slug}",
        _list_params(
            provider,
            page,
            limit,
            category=category,
            country=country,
            year=year,
            sort_lang=sort_lang,
            sort_field=sort_field,
            sort_type=sort_type,
        ),
    )


async def movie_list_by_year(
    year: int,
    provider: str | None = None,
    page: int = 1,
    limit: int = 10,
    category: str | None = None,
    country: str | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict:
    return await _get(
        f"/api/movies/years/{year}",
        _list_params(
            provider,
            page,
            limit,
            category=category,
            country=country,
            sort_lang=sort_lang,
            sort_field=sort_field,
            sort_type=sort_type,
        ),
    )


async def movie_get_genres(provider: str | None = None) -> dict:
    return await _get("/api/movies/meta/genres", {"provider": _movie_provider(provider)})


async def movie_get_countries(provider: str | None = None) -> dict:
    return await _get("/api/movies/meta/countries", {"provider": _movie_provider(provider)})
