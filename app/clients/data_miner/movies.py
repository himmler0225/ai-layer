from typing import Any

from app.clients import config as dm_config
from app.clients.data_miner._http import get as _get


def _movie_provider(provider: str | None = None) -> str:
    """(Nội bộ) Movie provider `_movie_provider`.

    Args:
        provider: (str | None, mặc định None) Tham số `provider`.

    Returns:
        (str) Kết quả trả về."""
    return (provider or dm_config.movie_default_provider()).strip().lower()


def _movie_filters(**kwargs: Any) -> dict[str, Any]:
    """(Nội bộ) Movie filters `_movie_filters`.

    Args:
        **kwargs: (Any) Tham số `**kwargs`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
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
    """(Nội bộ) Liệt kê params `_list_params`.

    Args:
        provider: (str | None) Tham số `provider`.
        page: (int) Tham số `page`.
        limit: (int) Tham số `limit`.
        category: (str | None, mặc định None) Tham số `category`.
        country: (str | None, mặc định None) Tham số `country`.
        year: (int | None, mặc định None) Tham số `year`.
        sort_lang: (str | None, mặc định None) Tham số `sort_lang`.
        sort_field: (str | None, mặc định None) Tham số `sort_field`.
        sort_type: (str | None, mặc định None) Tham số `sort_type`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
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
    """Movie search (async).

    Args:
        keyword: (str) Tham số `keyword`.
        provider: (str | None, mặc định None) Tham số `provider`.
        page: (int, mặc định 1) Tham số `page`.
        limit: (int, mặc định 10) Tham số `limit`.

    Returns:
        (dict) Kết quả trả về."""
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
    """Movie get detail (async).

    Args:
        slug: (str) Tham số `slug`.
        provider: (str | None, mặc định None) Tham số `provider`.

    Returns:
        (dict) Kết quả trả về."""
    return await _get(f"/api/movies/{slug}", {"provider": _movie_provider(provider)})


async def movie_list_new(provider: str | None = None, page: int = 1) -> dict:
    """Movie list new (async).

    Args:
        provider: (str | None, mặc định None) Tham số `provider`.
        page: (int, mặc định 1) Tham số `page`.

    Returns:
        (dict) Kết quả trả về."""
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
    """Movie list by type (async).

    Args:
        movie_type: (str) Tham số `movie_type`.
        provider: (str | None, mặc định None) Tham số `provider`.
        page: (int, mặc định 1) Tham số `page`.
        limit: (int, mặc định 10) Tham số `limit`.
        category: (str | None, mặc định None) Tham số `category`.
        country: (str | None, mặc định None) Tham số `country`.
        year: (int | None, mặc định None) Tham số `year`.
        sort_lang: (str | None, mặc định None) Tham số `sort_lang`.
        sort_field: (str | None, mặc định None) Tham số `sort_field`.
        sort_type: (str | None, mặc định None) Tham số `sort_type`.

    Returns:
        (dict) Kết quả trả về."""
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
    """Movie list by genre (async).

    Args:
        slug: (str) Tham số `slug`.
        provider: (str | None, mặc định None) Tham số `provider`.
        page: (int, mặc định 1) Tham số `page`.
        limit: (int, mặc định 10) Tham số `limit`.
        category: (str | None, mặc định None) Tham số `category`.
        country: (str | None, mặc định None) Tham số `country`.
        year: (int | None, mặc định None) Tham số `year`.
        sort_lang: (str | None, mặc định None) Tham số `sort_lang`.
        sort_field: (str | None, mặc định None) Tham số `sort_field`.
        sort_type: (str | None, mặc định None) Tham số `sort_type`.

    Returns:
        (dict) Kết quả trả về."""
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
    """Movie list by country (async).

    Args:
        slug: (str) Tham số `slug`.
        provider: (str | None, mặc định None) Tham số `provider`.
        page: (int, mặc định 1) Tham số `page`.
        limit: (int, mặc định 10) Tham số `limit`.
        category: (str | None, mặc định None) Tham số `category`.
        country: (str | None, mặc định None) Tham số `country`.
        year: (int | None, mặc định None) Tham số `year`.
        sort_lang: (str | None, mặc định None) Tham số `sort_lang`.
        sort_field: (str | None, mặc định None) Tham số `sort_field`.
        sort_type: (str | None, mặc định None) Tham số `sort_type`.

    Returns:
        (dict) Kết quả trả về."""
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
    """Movie list by year (async).

    Args:
        year: (int) Tham số `year`.
        provider: (str | None, mặc định None) Tham số `provider`.
        page: (int, mặc định 1) Tham số `page`.
        limit: (int, mặc định 10) Tham số `limit`.
        category: (str | None, mặc định None) Tham số `category`.
        country: (str | None, mặc định None) Tham số `country`.
        sort_lang: (str | None, mặc định None) Tham số `sort_lang`.
        sort_field: (str | None, mặc định None) Tham số `sort_field`.
        sort_type: (str | None, mặc định None) Tham số `sort_type`.

    Returns:
        (dict) Kết quả trả về."""
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
    """Movie get genres (async).

    Args:
        provider: (str | None, mặc định None) Tham số `provider`.

    Returns:
        (dict) Kết quả trả về."""
    return await _get("/api/movies/meta/genres", {"provider": _movie_provider(provider)})


async def movie_get_countries(provider: str | None = None) -> dict:
    """Movie get countries (async).

    Args:
        provider: (str | None, mặc định None) Tham số `provider`.

    Returns:
        (dict) Kết quả trả về."""
    return await _get("/api/movies/meta/countries", {"provider": _movie_provider(provider)})
