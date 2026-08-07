from typing import Any

from app.clients import config as dm_config
from app.clients.data_miner._http import get as _get


def _movie_provider(provider: str | None = None) -> str:
    """Normalize a movie provider name, defaulting to the configured provider.

    Args:
        provider: Explicit provider name, or `None` to use the default.

    Returns:
        The lowercased, trimmed provider name."""
    return (provider or dm_config.movie_default_provider()).strip().lower()


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
        provider: Movie provider name, or `None` for the default.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        A params dict with `provider`, `page`, `limit`, plus any non-empty
        optional filters."""
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
    """Search movies by keyword via the data-miner service.

    Args:
        keyword: Search text.
        provider: Movie provider name, or `None` for the default.
        page: Page number to fetch.
        limit: Number of results per page.

    Returns:
        The data-miner search response (dict)."""
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
    """Fetch full details for a single movie by its slug.

    Args:
        slug: The movie's unique slug identifier.
        provider: Movie provider name, or `None` for the default.

    Returns:
        The data-miner movie detail response (dict)."""
    return await _get(f"/api/movies/{slug}", {"provider": _movie_provider(provider)})


async def movie_list_new(provider: str | None = None, page: int = 1) -> dict:
    """List newly added movies.

    Args:
        provider: Movie provider name, or `None` for the default.
        page: Page number to fetch.

    Returns:
        The data-miner "new movies" list response (dict)."""
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
    """List movies by type (e.g. series, single, cartoon), with optional filters.

    Args:
        movie_type: The movie type/category slug to filter by.
        provider: Movie provider name, or `None` for the default.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The data-miner movie list response (dict)."""
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
    """List movies belonging to a given genre, with optional filters.

    Args:
        slug: The genre's unique slug identifier.
        provider: Movie provider name, or `None` for the default.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The data-miner movie list response (dict)."""
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
        provider: Movie provider name, or `None` for the default.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        year: Optional release-year filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The data-miner movie list response (dict)."""
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
        provider: Movie provider name, or `None` for the default.
        page: Page number to fetch.
        limit: Number of results per page.
        category: Optional category filter.
        country: Optional country filter.
        sort_lang: Optional sort language.
        sort_field: Optional field to sort by.
        sort_type: Optional sort direction/type.

    Returns:
        The data-miner movie list response (dict)."""
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
        provider: Movie provider name, or `None` for the default.

    Returns:
        The data-miner genres metadata response (dict)."""
    return await _get("/api/movies/meta/genres", {"provider": _movie_provider(provider)})


async def movie_get_countries(provider: str | None = None) -> dict:
    """List the available movie countries for a provider.

    Args:
        provider: Movie provider name, or `None` for the default.

    Returns:
        The data-miner countries metadata response (dict)."""
    return await _get("/api/movies/meta/countries", {"provider": _movie_provider(provider)})
