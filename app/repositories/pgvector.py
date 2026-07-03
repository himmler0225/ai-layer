def vector_literal(vec: list[float]) -> str:
    """Vector literal.

    Args:
        vec: (list[float]) Tham số `vec`.

    Returns:
        (str) Kết quả trả về."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
