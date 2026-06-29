from __future__ import annotations
import app.config.settings as settings
from app.ingest.processing.quality import is_indexable_comment

def curate_review_rows(rows: list[dict], *, top_n: int | None=None) -> list[dict]:
    limit = top_n if top_n is not None else settings.CURATED_TOP_N
    filtered = [r for r in rows if is_indexable_comment(r.get('content', ''))]
    filtered.sort(key=lambda r: int(r.get('likes') or 0), reverse=True)
    curated: list[dict] = []
    for rank, row in enumerate(filtered[:limit], start=1):
        raw_id = row.get('id') or row.get('raw_review_id')
        if not raw_id:
            continue
        curated.append({'id': f"cur:{row.get('product_id', '')}:{raw_id}", 'raw_review_id': raw_id, 'rank': rank, 'likes': int(row.get('likes') or 0), 'content': row['content']})
    return curated

def merge_curated(existing: list[dict], new_rows: list[dict], *, top_n: int | None=None) -> list[dict]:
    limit = top_n if top_n is not None else settings.CURATED_TOP_N
    pool: list[dict] = []
    for row in existing:
        raw_id = row.get('raw_review_id') or row.get('id')
        if not raw_id:
            continue
        pool.append({'id': raw_id, 'content': row.get('content', ''), 'likes': int(row.get('likes') or 0), 'product_id': row.get('product_id', '')})
    pool.extend(new_rows)
    return curate_review_rows(pool, top_n=limit)
