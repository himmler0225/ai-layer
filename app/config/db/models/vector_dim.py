from pgvector.sqlalchemy import Vector
import app.config.settings as settings


def embedding_vector() -> Vector:
    """Build the pgvector column type sized to the configured embedding dimension.

    Returns:
        Vector: A pgvector column type with dimension `settings.EMBEDDING_DIM`.
    """
    return Vector(settings.EMBEDDING_DIM)
