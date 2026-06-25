from __future__ import annotations

import app.config.settings as _cfg
from app.utils.openai_client import get_openai_client

_BATCH_SIZE = 64


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Tạo vector embedding batch qua OpenAI (text-embedding-3-small).

    Dùng cho: video_chunks (flat), aspect_chunks (L2), aspect_summaries (L1).
    """
    if not texts:
        return []

    client = get_openai_client()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        response = await client.embeddings.create(
            model=_cfg.EMBEDDING_MODEL,
            input=batch,
            dimensions=_cfg.EMBEDDING_DIM,
        )
        ordered = sorted(response.data, key=lambda row: row.index)
        vectors.extend(row.embedding for row in ordered)

    return vectors