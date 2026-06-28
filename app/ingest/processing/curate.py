from __future__ import annotations

"""Lọc + chọn top review chất lượng trước khi đưa vào LLM summarize."""

import app.config.settings as settings
from app.ingest.processing.quality import is_indexable_comment


def curate_review_rows(rows: list[dict], *, top_n: int | None = None) -> list[dict]:
    """
    L3 → curated: lọc spam/ngắn, sort likes DESC, lấy top N.

    Input: list dict raw_reviews (id, content, likes, product_id).
    Output: rows cho replace_curated_reviews (id, raw_review_id, rank, likes, content).

    Chỉ curated mới vào pipeline tạo aspect_chunks (L2) và aspect_summaries (L1).
    """
    limit = top_n if top_n is not None else settings.CURATED_TOP_N
    filtered = [r for r in rows if is_indexable_comment(r.get("content", ""))]
    filtered.sort(key=lambda r: int(r.get("likes") or 0), reverse=True)

    curated: list[dict] = []
    for rank, row in enumerate(filtered[:limit], start=1):
        raw_id = row.get("id") or row.get("raw_review_id")
        if not raw_id:
            continue
        curated.append(
            {
                "id": f"cur:{row.get('product_id', '')}:{raw_id}",
                "raw_review_id": raw_id,
                "rank": rank,
                "likes": int(row.get("likes") or 0),
                "content": row["content"],
            }
        )
    return curated


def merge_curated(
    existing: list[dict], new_rows: list[dict], *, top_n: int | None = None
) -> list[dict]:
    """Gộp curated hiện có với batch mới — không cần load toàn bộ raw."""
    limit = top_n if top_n is not None else settings.CURATED_TOP_N
    pool: list[dict] = []
    for row in existing:
        raw_id = row.get("raw_review_id") or row.get("id")
        if not raw_id:
            continue
        pool.append(
            {
                "id": raw_id,
                "content": row.get("content", ""),
                "likes": int(row.get("likes") or 0),
                "product_id": row.get("product_id", ""),
            }
        )
    pool.extend(new_rows)
    return curate_review_rows(pool, top_n=limit)
