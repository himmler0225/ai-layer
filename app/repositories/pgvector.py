def vector_literal(vec: list[float]) -> str:
    """Format a float vector as a pgvector literal string.

    Args:
        vec: Embedding values.

    Returns:
        A "[v1,v2,...]" string suitable for casting to `vector` in raw SQL.
    """
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
