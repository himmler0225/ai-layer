from __future__ import annotations

import json

import app.config.settings as settings
from app.ai.router import TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY
from app.config.logger import Logger
from app.ingest.processing.embeddings import embed_texts
from app.repositories.aspect_chunks import (delete_aspect_chunks_for_product,
                                            upsert_aspect_chunks)
from app.repositories.aspect_summaries import upsert_aspect_summary
from app.repositories.curated_reviews import get_curated_reviews
from app.repositories.products import get_product, upsert_product
from app.repositories.raw_reviews import count_raw_reviews
from app.services import prompts as rag_prompts
from app.services.chatgpt import complete_json

logger = Logger.get(__name__)

ASPECTS = [
    "battery",
    "camera",
    "screen",
    "performance",
    "design",
    "price",
    "software",
    "durability",
    "other",
]

_MAX_CURATED_FOR_LLM = 200


def _parse_json(raw: str) -> dict | list | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _fallback_group(curated: list[dict]) -> list[dict]:
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


async def _llm_group_aspects(curated: list[dict], *, product_name: str) -> list[dict]:
    """LLM nhóm curated reviews theo aspect → rows cho aspect_chunks (L2)."""
    if not curated:
        return []

    lines = []
    for c in curated[:_MAX_CURATED_FOR_LLM]:
        rid = c.get("raw_review_id") or c.get("id", "")
        likes = c.get("likes", 0)
        content = (c.get("content") or "")[:500]
        lines.append(f"- id={rid} likes={likes}: {content}")

    prompt = rag_prompts.ASPECT_GROUP_PROMPT.format(
        product=product_name,
        aspects=", ".join(ASPECTS),
        reviews="\n".join(lines),
    )

    try:
        raw = await complete_json(
            prompt,
            rag_prompts.ASPECT_GROUP_SYSTEM,
            max_tokens=settings.OPENAI_TOOL_MAX_TOKENS,
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
                if (
                    not isinstance(g, dict)
                    or not g.get("aspect")
                    or not g.get("content")
                ):
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
        logger.warning("[summarize] group_aspects LLM failed: %s", exc)

    return _fallback_group(curated)


async def _llm_summarize_aspect(
    aspect: str, chunk_content: str, *, product_name: str
) -> dict:
    """LLM tóm tắt một aspect → row aspect_summaries (L1)."""
    prompt = rag_prompts.ASPECT_SUMMARY_PROMPT.format(
        product=product_name,
        aspect=aspect,
        content=chunk_content[:6000],
    )
    try:
        raw = await complete_json(
            prompt,
            rag_prompts.ASPECT_SUMMARY_SYSTEM,
            max_tokens=settings.OPENAI_TOOL_MAX_TOKENS,
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
        logger.warning(
            "[summarize] summarize_aspect LLM failed aspect=%s: %s", aspect, exc
        )

    return {
        "summary": f"Tóm tắt {aspect} cho {product_name}: {chunk_content[:300]}...",
        "pros": [],
        "cons": [],
        "positive_percent": None,
    }


async def handle_product_summarize(envelope: dict) -> None:
    """Job nền: curated → aspect_chunks (L2) + aspect_summaries (L1) + embed."""
    payload = envelope.get("payload") or {}
    product_id = payload.get("product_id") or envelope.get("video_id")
    if not product_id:
        return

    product = await get_product(product_id)
    product_name = (product or {}).get("name") or product_id

    curated = await get_curated_reviews(product_id, limit=settings.CURATED_TOP_N)
    if not curated:
        logger.warning("[summarize] no curated product=%s", product_id)
        return

    groups = await _llm_group_aspects(curated, product_name=product_name)
    aspects = [g["aspect"] for g in groups]

    chunk_rows = []
    for g in groups:
        chunk_rows.append(
            {
                "id": f"chk:{product_id}:{g['aspect']}",
                "product_id": product_id,
                "aspect": g["aspect"],
                "content": g["content"],
                "review_ids": g.get("review_ids") or [],
                "positive_percent": g.get("positive_percent"),
                "negative_percent": g.get("negative_percent"),
            }
        )

    await delete_aspect_chunks_for_product(product_id, keep_aspects=aspects)

    vectors = await embed_texts([r["content"] for r in chunk_rows])
    for row, vec in zip(chunk_rows, vectors):
        row["embedding"] = vec
    await upsert_aspect_chunks(chunk_rows)

    for row in chunk_rows:
        aspect = row["aspect"]
        meta = await _llm_summarize_aspect(
            aspect, row["content"], product_name=product_name
        )
        summary_vec = (await embed_texts([meta["summary"]]))[0]
        await upsert_aspect_summary(
            id=f"sum:{product_id}:{aspect}",
            product_id=product_id,
            aspect=aspect,
            summary=meta["summary"],
            pros=meta.get("pros") or [],
            cons=meta.get("cons") or [],
            positive_percent=meta.get("positive_percent"),
            source_chunk_ids=[row["id"]],
            embedding=summary_vec,
        )

    meta = dict((product or {}).get("metadata") or {})
    meta["last_summarize_raw_count"] = await count_raw_reviews(product_id)
    meta["summarized_at"] = envelope.get("fetched_at") or ""
    await upsert_product(
        id=product_id,
        name=product_name,
        platform=(product or {}).get("platform") or "mixed",
        metadata=meta,
    )

    logger.info(
        "[summarize] done product=%s chunks=%d aspects=%s",
        product_id,
        len(chunk_rows),
        aspects,
    )
