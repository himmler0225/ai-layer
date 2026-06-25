"""Kích thước vector embedding — đồng bộ với EMBEDDING_DIM trong settings."""

from pgvector.sqlalchemy import Vector

import app.config.settings as _cfg


def embedding_vector() -> Vector:
    return Vector(_cfg.EMBEDDING_DIM)
