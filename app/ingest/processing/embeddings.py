from app.ai.router import get_router

_BATCH_SIZE = 64


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Compute embedding vectors for a list of texts, batching requests to the router.

    Args:
        texts: Texts to embed.

    Returns:
        A list of embedding vectors, one per input text, in the same order; []
        if `texts` is empty.
    """
    if not texts:
        return []
    router = get_router()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        vectors.extend(await router.embed_texts(batch))
    return vectors
