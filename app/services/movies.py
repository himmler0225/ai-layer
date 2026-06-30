from __future__ import annotations

from typing import Any, Dict, Optional

import app.config.settings as settings
from app.clients import movie_api


def _provider(value: Optional[str]) -> str:
    return value or settings.MOVIE_DEFAULT_PROVIDER


async def search(
    keyword: str,
    *,
    provider: Optional[str] = None,
    page: int = 1,
    limit: int = 24,
) -> Dict[str, Any]:
    return await movie_api.search(_provider(provider), keyword=keyword, page=page, limit=limit)


async def get_detail(slug: str, *, provider: Optional[str] = None) -> Dict[str, Any]:
    return await movie_api.get_detail(_provider(provider), slug)


async def list_new(*, provider: Optional[str] = None, page: int = 1) -> Dict[str, Any]:
    return await movie_api.get_new(_provider(provider), page=page)


async def list_by_type(
    movie_type: str,
    *,
    provider: Optional[str] = None,
    page: int = 1,
    limit: int = 24,
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = None,
    sort_lang: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_type: Optional[str] = None,
) -> Dict[str, Any]:
    return await movie_api.list_by_type(
        _provider(provider),
        movie_type,
        page=page,
        limit=limit,
        category=category,
        country=country,
        year=year,
        sort_lang=sort_lang,
        sort_field=sort_field,
        sort_type=sort_type,
    )


async def list_by_genre(
    slug: str,
    *,
    provider: Optional[str] = None,
    page: int = 1,
    limit: int = 24,
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = None,
    sort_lang: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_type: Optional[str] = None,
) -> Dict[str, Any]:
    return await movie_api.list_by_genre(
        _provider(provider),
        slug,
        page=page,
        limit=limit,
        category=category,
        country=country,
        year=year,
        sort_lang=sort_lang,
        sort_field=sort_field,
        sort_type=sort_type,
    )


async def list_by_country(
    slug: str,
    *,
    provider: Optional[str] = None,
    page: int = 1,
    limit: int = 24,
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = None,
    sort_lang: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_type: Optional[str] = None,
) -> Dict[str, Any]:
    return await movie_api.list_by_country(
        _provider(provider),
        slug,
        page=page,
        limit=limit,
        category=category,
        country=country,
        year=year,
        sort_lang=sort_lang,
        sort_field=sort_field,
        sort_type=sort_type,
    )


async def list_by_year(
    year: int,
    *,
    provider: Optional[str] = None,
    page: int = 1,
    limit: int = 24,
    category: Optional[str] = None,
    country: Optional[str] = None,
    sort_lang: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_type: Optional[str] = None,
) -> Dict[str, Any]:
    return await movie_api.list_by_year(
        _provider(provider),
        year,
        page=page,
        limit=limit,
        category=category,
        country=country,
        sort_lang=sort_lang,
        sort_field=sort_field,
        sort_type=sort_type,
    )


async def get_genres(*, provider: Optional[str] = None) -> Dict[str, Any]:
    return await movie_api.get_genres(_provider(provider))


async def get_countries(*, provider: Optional[str] = None) -> Dict[str, Any]:
    return await movie_api.get_countries(_provider(provider))


async def proxy_webp(*, provider: Optional[str] = None, image_url: str) -> Dict[str, Any]:
    return await movie_api.proxy_webp(_provider(provider), image_url=image_url)
