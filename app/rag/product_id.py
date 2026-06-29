from __future__ import annotations
from app.ingest.mappers.social_review import slugify_product_id
__all__ = ['slugify_product_id', 'resolve_product_id']

async def resolve_product_id(name: str) -> str | None:
    """Giải quyết product id (async).

    Args:
        name: (str) Tham số `name`.

    Returns:
        (str | None) Kết quả trả về."""
    from app.repositories.products import exists_product
    slug = slugify_product_id(name)
    if not slug or slug == 'unknown-product':
        return None
    return slug if await exists_product(slug) else None
