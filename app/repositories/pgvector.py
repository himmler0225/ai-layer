from __future__ import annotations

"""Helper pgvector — literal format cho cosine search."""


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
