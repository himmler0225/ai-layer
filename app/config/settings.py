import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _env_list(key: str, default: str = "") -> list[str]:
    """(Nội bộ) Env list.

    Args:
        key: (str) Tham số `key`.
        default: (str, mặc định '') Tham số `default`.

    Returns:
        (list[str]) Kết quả trả về."""
    return [item.strip() for item in os.getenv(key, default).split(",") if item.strip()]


APP_ENV: str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
# Embedding: LLM_EMBEDDING_PROVIDER hoặc cùng provider đang active trong AI_MODELS.
LLM_EMBEDDING_PROVIDER: str = os.getenv("LLM_EMBEDDING_PROVIDER", "").strip().lower()
API_KEYS: list[str] = _env_list("API_KEYS")
CORS_ORIGINS: list[str] = _env_list("CORS_ORIGINS", "http://localhost:3000")

DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "1"))

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

SUPABASE_TOKEN_TTL: int = 3600
HISTORY_SESSIONS_TTL: int = 300
HISTORY_MESSAGES_TTL: int = 600
REMOTE_CONFIG_TTL: int = int(os.getenv("REMOTE_CONFIG_TTL", "5"))

GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "")
GEOIP_CACHE_TTL: int = int(os.getenv("GEOIP_CACHE_TTL", "3600"))
GEOIP_CACHE_MAX: int = int(os.getenv("GEOIP_CACHE_MAX", "500"))

MOVIE_DEFAULT_PROVIDER: str = os.getenv("MOVIE_DEFAULT_PROVIDER", "kkphim").strip().lower()


from app.ingest.config import INGEST_ENABLED
from app.rag.config import (
    CACHE_TTL_DAYS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    RAG_ENABLED,
    RAG_MIN_SCORE,
    RAG_TOP_K,
)

_REMOTE: dict[str, Any] = {}
_remote_ready = False


def ensure_remote_defaults() -> None:
    """Ensure remote defaults.

    Returns:
        (None) Kết quả trả về."""
    global _remote_ready
    if _remote_ready:
        return
    from app.config.defaults import apply_env_fallbacks, build_settings_defaults, load_schema

    schema = load_schema()
    _REMOTE.update(build_settings_defaults(schema))
    apply_env_fallbacks(_REMOTE, schema)
    _remote_ready = True


def set_remote(name: str, value: Any) -> None:
    """Set remote.

    Args:
        name: (str) Tham số `name`.
        value: (Any) Tham số `value`.

    Returns:
        (None) Kết quả trả về."""
    ensure_remote_defaults()
    _REMOTE[name] = value


def update_remote(values: dict[str, Any]) -> None:
    """Update remote.

    Args:
        values: (dict[str, Any]) Tham số `values`.

    Returns:
        (None) Kết quả trả về."""
    ensure_remote_defaults()
    _REMOTE.update(values)


def get_remote(name: str, default: Any = None) -> Any:
    """Lấy remote.

    Args:
        name: (str) Tham số `name`.
        default: (Any, mặc định None) Tham số `default`.

    Returns:
        (Any) Kết quả trả về."""
    ensure_remote_defaults()
    return _REMOTE.get(name, default)


def __getattr__(name: str) -> Any:
    """Ủy quyền đọc attribute khi không tìm thấy trên module.

    Args:
        name: (str) Tham số `name`.

    Returns:
        (Any) Kết quả trả về."""
    if name.startswith("_"):
        raise AttributeError(name)
    ensure_remote_defaults()
    if name in _REMOTE:
        return _REMOTE[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
