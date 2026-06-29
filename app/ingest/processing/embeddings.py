from __future__ import annotations
import app.config.settings as settings
from app.ai.router import get_router
_BATCH_SIZE = 64

async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    router = get_router()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start:start + _BATCH_SIZE]
        vectors.extend(await router.embed_texts(batch))
    return vectors
