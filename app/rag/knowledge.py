from __future__ import annotations
from datetime import datetime, timedelta, timezone
import app.config.settings as settings
from app.repositories.aspect_summaries import get_aspect_summaries
from app.repositories.curated_reviews import count_curated_reviews
from app.repositories.products import exists_product

async def product_has_knowledge(product_id: str) -> bool:
    if not product_id or not await exists_product(product_id):
        return False
    summaries = await get_aspect_summaries(product_id)
    if summaries:
        return True
    return await count_curated_reviews(product_id) >= 20

async def is_product_fresh(product_id: str, days: int | None=None) -> bool:
    ttl_days = days if days is not None else settings.CACHE_TTL_DAYS
    summaries = await get_aspect_summaries(product_id)
    if not summaries:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    for row in summaries:
        updated = row.get('updated_at')
        if updated is None:
            return True
        if isinstance(updated, datetime):
            ts = updated if updated.tzinfo else updated.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                return True
    return False
