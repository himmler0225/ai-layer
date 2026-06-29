from pgvector.sqlalchemy import Vector
import app.config.settings as settings

def embedding_vector() -> Vector:
    return Vector(settings.EMBEDDING_DIM)
