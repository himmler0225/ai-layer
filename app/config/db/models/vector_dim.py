from pgvector.sqlalchemy import Vector
import app.config.settings as settings


def embedding_vector() -> Vector:
    """Embedding vector.

    Returns:
        (Vector) Kết quả trả về."""
    return Vector(settings.EMBEDDING_DIM)
