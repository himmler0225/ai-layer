from __future__ import annotations
import app.config.settings as settings
from app.config.logger import Logger
from app.ingest.mappers.social_review import map_social_raw_review, slugify_product_id
from app.ingest.processing.curate import merge_curated
from app.ingest.producer.publisher import publish
from app.ingest.schemas import ROUTING_SUMMARIZE
from app.repositories.aspect_summaries import get_aspect_summaries
from app.repositories.curated_reviews import get_curated_reviews, replace_curated_reviews
from app.repositories.products import get_product, upsert_product
from app.repositories.raw_reviews import count_raw_reviews, upsert_raw_reviews
logger = Logger.get(__name__)
_MIN_RAW_FOR_SUMMARIZE = 20
_RE_SUMMARIZE_DELTA = 50

async def _should_queue_summarize(product_id: str, total_raw: int) -> bool:
    """(Nội bộ) Should queue summarize (async).

    Args:
        product_id: (str) Tham số `product_id`.
        total_raw: (int) Tham số `total_raw`.

    Returns:
        (bool) Kết quả trả về."""
    if total_raw < _MIN_RAW_FOR_SUMMARIZE:
        return False
    summaries = await get_aspect_summaries(product_id)
    if not summaries:
        return True
    product = await get_product(product_id)
    meta = (product or {}).get('metadata') or {}
    last = int(meta.get('last_summarize_raw_count') or 0)
    return total_raw - last >= _RE_SUMMARIZE_DELTA

async def sync_comments_to_product_rag(*, product_hint: str, platform: str, video_id: str, raw_comments: list[dict]) -> str | None:
    """Đồng bộ comments to product rag (async).

    Args:
        product_hint: (str) Tham số `product_hint`.
        platform: (str) Tham số `platform`.
        video_id: (str) Tham số `video_id`.
        raw_comments: (list[dict]) Tham số `raw_comments`.

    Returns:
        (str | None) Kết quả trả về."""
    hint = (product_hint or '').strip()
    if not hint:
        return None
    product_id = slugify_product_id(hint)
    existing = await get_product(product_id)
    meta = dict((existing or {}).get('metadata') or {})
    await upsert_product(id=product_id, name=hint, platform=platform, metadata=meta)
    rows: list[dict] = []
    for raw in raw_comments:
        row = map_social_raw_review(product_id, platform, video_id, raw)
        if row:
            rows.append(row)
    if not rows:
        return product_id
    await upsert_raw_reviews(rows)
    existing = await get_curated_reviews(product_id, limit=getattr(settings, "AGENT_CURATED_TOP_N", 300))
    curated = merge_curated(existing, rows)
    await replace_curated_reviews(product_id, curated)
    total = await count_raw_reviews(product_id)
    if await _should_queue_summarize(product_id, total):
        await publish(ROUTING_SUMMARIZE, platform=platform, video_id=product_id, product_hint=hint, payload={'product_id': product_id})
        logger.info('[rag_sync] queued summarize product=%s raw=%d', product_id, total)
    return product_id
