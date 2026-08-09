"""Movie catalog client — calls movie-aggregator-api directly (kkphim/ophim/vsmov,
with automatic multi-source fallback), replacing the old data-miner movie crawler.

Function signatures match the old `app.clients.data_miner.movies` module so
callers only needed an import change."""

from typing import Any

import app.config.settings as settings
from app.clients.movie_aggregator._http import get as _get


def _source_param(provider: str | None = None) -> dict[str, str]:
    """Build the `source` query param, pinning an upstream or omitting it.

    Args:
        provider: Explicit provider name, or `None` to use the configured
            default.

    Returns:
        `{"source": <provider>}` if a provider is pinned (explicitly or via
        `MOVIE_DEFAULT_PROVIDER`), otherwise `{}` — which lets
        movie-aggregator-api auto-fallback across kkphim -> ophim -> vsmov."""
    p = (provider or settings.MOVIE_DEFAULT_PROVIDER).strip().lower()
    return {"source": p} if p else {}


def _movie_filters(**kwargs: Any) -> dict[str, Any]:
    """Drop `None`/empty-string values from a set of optional filter kwargs.

    Args:
        **kwargs: Candidate filter values (e.g. category, country, year).

    Returns:
        A dict containing only the kwargs with a non-`None`, non-empty value."""
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
    """Build the common query params for the movie list-by-* endpoints.

    Args:
        provider: Movie provider name, or `None` to auto-fallback.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        A params dict with `page`, `limit`, an optional `source`, plus any
        non-empty optional filters."""
    return {
        "page": page,
        "limit": limit,
        **_source_param(provider),
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
    """Search movies by keyword via movie-aggregator-api.

    Args:
        keyword: Search text.
        provider: Movie provider name, or `None` to auto-fallback.
        page: Page number to fetch.
        limit: Number of results per page.

    Returns:
        The movie-aggregator-api search response (dict)."""
    return await _get(
        "/api/movies/search",
        {"keyword": keyword, "page": page, "limit": limit, **_source_param(provider)},
    )


async def movie_get_detail(slug: str, provider: str | None = None) -> dict:
    """Fetch full details for a single movie by its slug.

    Args:
        slug: The movie's unique slug identifier.
        provider: Movie provider name, or `None` to auto-fallback.

    Returns:
        The movie-aggregator-api movie detail response (dict)."""
    return await _get(f"/api/movies/{slug}", _source_param(provider))


async def movie_list_new(provider: str | None = None, page: int = 1) -> dict:
    """List newly added movies.

    Args:
        provider: Movie provider name, or `None` to auto-fallback.
        page: Page number to fetch.

    Returns:
        The movie-aggregator-api "new movies" list response (dict)."""
    return await _get("/api/movies/new", {"page": page, **_source_param(provider)})


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
    """List movies by type (e.g. series, single, cartoon), with optional filters.

    Args:
        movie_type: The movie type/category slug to filter by.
        provider: Movie provider name, or `None` to auto-fallback.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The movie-aggregator-api movie list response (dict)."""
    return await _get(
        f"/api/movies/type/{movie_type}",
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
    """List movies belonging to a given genre, with optional filters.

    Args:
        slug: The genre's unique slug identifier.
        provider: Movie provider name, or `None` to auto-fallback.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The movie-aggregator-api movie list response (dict)."""
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
    """List movies from a given country, with optional filters.

    Args:
        slug: The country's unique slug identifier.
        provider: Movie provider name, or `None` to auto-fallback.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The movie-aggregator-api movie list response (dict)."""
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
    """List movies released in a given year, with optional filters.

    Args:
        year: The release year to filter by.
        provider: Movie provider name, or `None` to auto-fallback.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The movie-aggregator-api movie list response (dict)."""
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
    """List the available movie genres for a provider.

    Args:
        provider: Movie provider name, or `None` to auto-fallback.

    Returns:
        The movie-aggregator-api genres metadata response (dict)."""
    return await _get("/api/movies/meta/genres", _source_param(provider))


async def movie_get_countries(provider: str | None = None) -> dict:
    """List the available movie countries for a provider.

    Args:
        provider: Movie provider name, or `None` to auto-fallback.

    Returns:
        The movie-aggregator-api countries metadata response (dict)."""
    return await _get("/api/movies/meta/countries", _source_param(provider))
