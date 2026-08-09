import json
import app.config.settings as settings
from app.ai.router import TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY, max_tokens_for_task
from app.config.logger import Logger, log_event
from app.ingest.processing.embeddings import embed_texts
from app.repositories.aspect_chunks import delete_aspect_chunks_for_movie, upsert_aspect_chunks
from app.repositories.aspect_summaries import upsert_aspect_summary
from app.repositories.curated_reviews import get_curated_reviews
from app.repositories.movies import get_movie, upsert_movie
from app.repositories.raw_reviews import count_raw_reviews
from app.services import prompts as rag_prompts
from app.utils.llm_responses import complete_json

logger = Logger.get(__name__)
ASPECTS = ["battery", "camera", "screen", "performance", "design", "price", "software", "durability", "other"]
_MAX_CURATED_FOR_LLM = 200


def _parse_json(raw: str) -> dict | list | None:
    """Parse an LLM response as JSON, stripping a leading/trailing markdown code fence.

    Args:
        raw: Raw text returned by the LLM, possibly wrapped in a ```...``` fence.

    Returns:
        The parsed JSON value (dict or list), or None if it isn't valid JSON.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _fallback_group(curated: list[dict]) -> list[dict]:
    """Build a single catch-all "other" aspect group when LLM grouping is unavailable.

    Args:
        curated: Curated review rows; only the first 50 are used.

    Returns:
        A single-item list containing one aspect group dict (aspect="other") whose
        content is the concatenation of the review texts, with placeholder
        positive/negative percentages.
    """
    texts = [c["content"] for c in curated[:50]]
    return [
        {
            "aspect": "other",
            "review_ids": [c.get("raw_review_id") for c in curated[:50]],
            "content": "\n".join(texts),
            "positive_percent": 70.0,
            "negative_percent": 30.0,
        }
    ]


async def _llm_group_aspects(curated: list[dict], *, movie_name: str) -> list[dict]:
    """Ask the LLM to group curated reviews into aspect buckets (battery, camera, etc.).

    Formats up to `_MAX_CURATED_FOR_LLM` curated reviews into a prompt, asks the LLM
    to cluster them by aspect, and validates/normalizes the returned groups (unknown
    aspect labels fall back to "other"). Falls back to `_fallback_group` if the LLM
    call fails or returns nothing usable.

    Args:
        curated: Curated review rows to group.
        movie_name: Movie/product name used to fill in the grouping prompt.

    Returns:
        A list of aspect group dicts, each with "aspect", "review_ids", "content",
        "positive_percent", and "negative_percent". Empty list if `curated` is empty.
    """
    if not curated:
        return []
    lines = []
    for c in curated[:_MAX_CURATED_FOR_LLM]:
        rid = c.get("raw_review_id") or c.get("id", "")
        likes = c.get("likes", 0)
        content = (c.get("content") or "")[:500]
        lines.append(f"- id={rid} likes={likes}: {content}")
    prompt = rag_prompts.ASPECT_GROUP_PROMPT.format(
        movie=movie_name, product=movie_name, aspects=", ".join(ASPECTS), reviews="\n".join(lines)
    )
    try:
        raw = await complete_json(
            prompt,
            rag_prompts.ASPECT_GROUP_SYSTEM,
            max_tokens=max_tokens_for_task(TASK_ASPECT_GROUP),
            task=TASK_ASPECT_GROUP,
        )
        parsed = _parse_json(raw)
        groups = None
        if isinstance(parsed, dict):
            groups = parsed.get("groups") or parsed.get("items")
        elif isinstance(parsed, list):
            groups = parsed
        if groups:
            valid = []
            for g in groups:
                if not isinstance(g, dict) or not g.get("aspect") or (not g.get("content")):
                    continue
                aspect = str(g["aspect"]).lower().strip()
                if aspect not in ASPECTS:
                    aspect = "other"
                valid.append(
                    {
                        "aspect": aspect,
                        "review_ids": g.get("review_ids") or [],
                        "content": str(g["content"])[:8000],
                        "positive_percent": g.get("positive_percent"),
                        "negative_percent": g.get("negative_percent"),
                    }
                )
            if valid:
                return valid
    except Exception as exc:
        logger.warning(log_event("summarize", "group aspects llm failed", error=exc))
    return _fallback_group(curated)


async def _llm_summarize_aspect(aspect: str, chunk_content: str, *, movie_name: str) -> dict:
    """Ask the LLM to summarize one aspect's grouped review content.

    Args:
        aspect: Aspect label (e.g. "battery", "camera") being summarized.
        chunk_content: Concatenated review content for this aspect (truncated to 6000 chars).
        movie_name: Movie/product name used to fill in the summarization prompt.

    Returns:
        A dict with "summary", "pros", "cons", and "positive_percent". If the LLM
        call fails or returns no usable summary, falls back to a generic templated
        summary with empty pros/cons and positive_percent=None.
    """
    prompt = rag_prompts.ASPECT_SUMMARY_PROMPT.format(
        movie=movie_name, product=movie_name, aspect=aspect, content=chunk_content[:6000]
    )
    try:
        raw = await complete_json(
            prompt,
            rag_prompts.ASPECT_SUMMARY_SYSTEM,
            max_tokens=max_tokens_for_task(TASK_ASPECT_SUMMARY),
            task=TASK_ASPECT_SUMMARY,
        )
        parsed = _parse_json(raw)
        if isinstance(parsed, dict) and parsed.get("summary"):
            return {
                "summary": str(parsed["summary"])[:2000],
                "pros": parsed.get("pros") or [],
                "cons": parsed.get("cons") or [],
                "positive_percent": parsed.get("positive_percent"),
            }
    except Exception as exc:
        logger.warning(log_event("summarize", "summarize aspect llm failed", aspect=aspect, error=exc))
    return {
        "summary": f"Tóm tắt {aspect} cho {movie_name}: {chunk_content[:300]}...",
        "pros": [],
        "cons": [],
        "positive_percent": None,
    }


async def handle_movie_summarize(envelope: dict) -> None:
    """Regenerate aspect summaries for a movie from its curated reviews.

    Loads curated reviews for the movie, groups them into aspects via the LLM,
    stores the resulting aspect chunks (with embeddings), summarizes each aspect
    via the LLM, stores the resulting aspect summaries (with embeddings), and
    updates the movie's metadata with the summarization bookkeeping (raw review
    count and timestamp).

    Args:
        envelope: Ingest envelope dict whose payload (or "video_id" fallback)
            contains "movie_id".

    Returns:
        None. Does nothing if there is no movie id or no curated reviews.
    """
    payload = envelope.get("payload") or {}
    movie_id = payload.get("movie_id") or envelope.get("video_id")
    if not movie_id:
        return
    movie_row = await get_movie(movie_id)
    movie_name = (movie_row or {}).get("name") or movie_id
    curated = await get_curated_reviews(movie_id, limit=getattr(settings, "AGENT_CURATED_TOP_N", 300))
    if not curated:
        logger.warning(log_event("summarize", "no curated reviews", movie_id=movie_id))
        return
    groups = await _llm_group_aspects(curated, movie_name=movie_name)
    aspects = [g["aspect"] for g in groups]
    chunk_rows = []
    for g in groups:
        chunk_rows.append(
            {
                "id": f"chk:{movie_id}:{g['aspect']}",
                "movie_id": movie_id,
                "aspect": g["aspect"],
                "content": g["content"],
                "review_ids": g.get("review_ids") or [],
                "positive_percent": g.get("positive_percent"),
                "negative_percent": g.get("negative_percent"),
            }
        )
    await delete_aspect_chunks_for_movie(movie_id, keep_aspects=aspects)
    vectors = await embed_texts([r["content"] for r in chunk_rows])
    for row, vec in zip(chunk_rows, vectors, strict=True):
        row["embedding"] = vec
    await upsert_aspect_chunks(chunk_rows)
    for row in chunk_rows:
        aspect = row["aspect"]
        meta = await _llm_summarize_aspect(aspect, row["content"], movie_name=movie_name)
        summary_vec = (await embed_texts([meta["summary"]]))[0]
        await upsert_aspect_summary(
            id=f"sum:{movie_id}:{aspect}",
            movie_id=movie_id,
            aspect=aspect,
            summary=meta["summary"],
            pros=meta.get("pros") or [],
            cons=meta.get("cons") or [],
            positive_percent=meta.get("positive_percent"),
            source_chunk_ids=[row["id"]],
            embedding=summary_vec,
        )
    meta = dict((movie_row or {}).get("metadata") or {})
    meta["last_summarize_raw_count"] = await count_raw_reviews(movie_id)
    meta["summarized_at"] = envelope.get("fetched_at") or ""
    await upsert_movie(
        id=movie_id, name=movie_name, platform=(movie_row or {}).get("platform") or "mixed", metadata=meta
    )
    logger.info(
        log_event("summarize", "complete", movie_id=movie_id, chunks=len(chunk_rows), aspects=aspects)
    )
