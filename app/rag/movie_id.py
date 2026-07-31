from app.ingest.mappers.social_review import slugify_movie_id

__all__ = ["slugify_movie_id", "resolve_movie_id"]


async def resolve_movie_id(name: str) -> str | None:
    """Giải quyết movie id (async).

    Args:
        name: (str) Tham số `name`.

    Returns:
        (str | None) Kết quả trả về."""
    from app.repositories.movies import exists_movie

    slug = slugify_movie_id(name)
    if not slug or slug == "unknown-movie":
        return None
    return slug if await exists_movie(slug) else None
