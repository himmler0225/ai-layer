from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.config.rate_limits import movies_rate_limit
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.schemas.response import ApiResponse
from app.services import movies as movies_service

router = APIRouter(prefix="/movies", dependencies=[Depends(verify_api_key)])

MovieProvider = Literal["kkphim", "ophim"]
MovieType = Literal[
    "phim-bo",
    "phim-le",
    "tv-shows",
    "hoat-hinh",
    "phim-vietsub",
    "phim-thuyet-minh",
    "phim-long-tieng",
]


def _filters(
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = None,
    sort_lang: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_type: Optional[str] = None,
) -> dict:
    return {
        "category": category,
        "country": country,
        "year": year,
        "sort_lang": sort_lang,
        "sort_field": sort_field,
        "sort_type": sort_type,
    }


@router.get("/search")
@limiter.limit(movies_rate_limit)
async def search_movies(
    request: Request,
    keyword: str = Query(..., min_length=1),
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
):
    return ApiResponse.ok(await movies_service.search(keyword, provider=provider, page=page, limit=limit))


@router.get("/new")
@limiter.limit(movies_rate_limit)
async def list_new_movies(
    request: Request,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
):
    return ApiResponse.ok(await movies_service.list_new(provider=provider, page=page))


@router.get("/meta/genres")
@limiter.limit(movies_rate_limit)
async def meta_genres(request: Request, provider: MovieProvider = "kkphim"):
    return ApiResponse.ok(await movies_service.get_genres(provider=provider))


@router.get("/meta/countries")
@limiter.limit(movies_rate_limit)
async def meta_countries(request: Request, provider: MovieProvider = "kkphim"):
    return ApiResponse.ok(await movies_service.get_countries(provider=provider))


@router.get("/meta/image-proxy")
@limiter.limit(movies_rate_limit)
async def image_proxy(
    request: Request,
    url: str = Query(..., min_length=1, description="URL ảnh phimimg.com (KKPhim only)"),
    provider: MovieProvider = "kkphim",
):
    return ApiResponse.ok(await movies_service.proxy_webp(provider=provider, image_url=url))


@router.get("/types/{movie_type}")
@limiter.limit(movies_rate_limit)
async def list_by_type(
    request: Request,
    movie_type: MovieType,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = Query(None, ge=1900, le=2100),
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    return ApiResponse.ok(
        await movies_service.list_by_type(
            movie_type,
            provider=provider,
            page=page,
            limit=limit,
            **_filters(category, country, year, sort_lang, sort_field, sort_type),
        )
    )


@router.get("/genres/{slug}")
@limiter.limit(movies_rate_limit)
async def list_by_genre(
    request: Request,
    slug: str,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = Query(None, ge=1900, le=2100),
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    return ApiResponse.ok(
        await movies_service.list_by_genre(
            slug,
            provider=provider,
            page=page,
            limit=limit,
            **_filters(category, country, year, sort_lang, sort_field, sort_type),
        )
    )


@router.get("/countries/{slug}")
@limiter.limit(movies_rate_limit)
async def list_by_country(
    request: Request,
    slug: str,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = Query(None, ge=1900, le=2100),
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    return ApiResponse.ok(
        await movies_service.list_by_country(
            slug,
            provider=provider,
            page=page,
            limit=limit,
            **_filters(category, country, year, sort_lang, sort_field, sort_type),
        )
    )


@router.get("/years/{year}")
@limiter.limit(movies_rate_limit)
async def list_by_year(
    request: Request,
    year: int,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    return ApiResponse.ok(
        await movies_service.list_by_year(
            year,
            provider=provider,
            page=page,
            limit=limit,
            **_filters(category, country, None, sort_lang, sort_field, sort_type),
        )
    )


@router.get("/{slug}")
@limiter.limit(movies_rate_limit)
async def get_movie(
    request: Request,
    slug: str,
    provider: MovieProvider = "kkphim",
):
    return ApiResponse.ok(await movies_service.get_detail(slug, provider=provider))
