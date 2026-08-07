import app.config.settings as settings
from app.ingest.processing.quality import is_indexable_comment


def curate_review_rows(rows: list[dict], *, top_n: int | None = None) -> list[dict]:
    """Filter, rank, and truncate raw review rows into the curated review shape.

    Drops rows whose content isn't indexable, sorts the remainder by likes
    (descending), and keeps the top `limit`, assigning each a 1-based rank.

    Args:
        rows: Raw review rows, each with at least "content", "likes", and an id
            under "id" or "raw_review_id".
        top_n: Max number of rows to keep; defaults to settings.AGENT_CURATED_TOP_N
            (or 300) when None.

    Returns:
        A list of curated review dicts with "id", "raw_review_id", "rank", "likes",
        and "content". Rows without a resolvable id are skipped.
    """
    limit = top_n if top_n is not None else getattr(settings, "AGENT_CURATED_TOP_N", 300)
    filtered = [r for r in rows if is_indexable_comment(r.get("content", ""))]
    filtered.sort(key=lambda r: int(r.get("likes") or 0), reverse=True)
    curated: list[dict] = []
    for rank, row in enumerate(filtered[:limit], start=1):
        raw_id = row.get("id") or row.get("raw_review_id")
        if not raw_id:
            continue
        curated.append(
            {
                "id": f"cur:{row.get('movie_id', '')}:{raw_id}",
                "raw_review_id": raw_id,
                "rank": rank,
                "likes": int(row.get("likes") or 0),
                "content": row["content"],
            }
        )
    return curated


def merge_curated(existing: list[dict], new_rows: list[dict], *, top_n: int | None = None) -> list[dict]:
    """Merge previously curated reviews with newly ingested rows and re-curate.

    Args:
        existing: Previously curated review rows.
        new_rows: Newly mapped raw review rows to merge in.
        top_n: Max number of rows to keep after merging; defaults to
            settings.AGENT_CURATED_TOP_N (or 300) when None.

    Returns:
        The re-curated (filtered, ranked, truncated) list of review dicts, as
        produced by `curate_review_rows`.
    """
    limit = top_n if top_n is not None else getattr(settings, "AGENT_CURATED_TOP_N", 300)
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
                "movie_id": row.get("movie_id", ""),
            }
        )
    pool.extend(new_rows)
    return curate_review_rows(pool, top_n=limit)
