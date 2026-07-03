"""RAG / embedding configuration."""

import os


def _env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


RAG_ENABLED: bool = _env_bool("RAG_ENABLED")
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "8"))
RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.65"))
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))
CACHE_TTL_DAYS: int = int(os.getenv("CACHE_TTL_DAYS", "7"))
