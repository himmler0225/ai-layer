import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _env_list(key: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable as a list of trimmed strings.

    Args:
        key: Environment variable name.
        default: Raw comma-separated fallback used if the variable is unset.

    Returns:
        list[str]: Non-empty, trimmed items from the comma-separated value.
    """
    return [item.strip() for item in os.getenv(key, default).split(",") if item.strip()]


APP_ENV: str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
# Embedding: uses LLM_EMBEDDING_PROVIDER, or falls back to whichever provider is active in AI_MODELS.
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

# Langfuse — agent tracing (optional; tracing is skipped if these are unset)
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

SUPABASE_TOKEN_TTL: int = 3600
HISTORY_SESSIONS_TTL: int = 300
HISTORY_MESSAGES_TTL: int = 600
REMOTE_CONFIG_TTL: int = int(os.getenv("REMOTE_CONFIG_TTL", "5"))

GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "")
GEOIP_CACHE_TTL: int = int(os.getenv("GEOIP_CACHE_TTL", "3600"))
GEOIP_CACHE_MAX: int = int(os.getenv("GEOIP_CACHE_MAX", "500"))

# Empty = let movie-aggregator-api auto-fallback across kkphim -> ophim -> vsmov.
MOVIE_DEFAULT_PROVIDER: str = os.getenv("MOVIE_DEFAULT_PROVIDER", "").strip().lower()
MOVIE_AGGREGATOR_URL: str = os.getenv("MOVIE_AGGREGATOR_URL", "http://localhost:3001").strip()
MOVIE_AGGREGATOR_TIMEOUT: float = float(os.getenv("MOVIE_AGGREGATOR_TIMEOUT", "20"))

# i18n — catalogs in app/i18n/locales/<code>.py; add codes here as you translate.
I18N_SUPPORTED_LOCALES: list[str] = _env_list("I18N_SUPPORTED_LOCALES", "vi,en")
I18N_DEFAULT_LOCALE: str = os.getenv("I18N_DEFAULT_LOCALE", "en").strip().lower() or "en"

from app.rag.config import CACHE_TTL_DAYS, EMBEDDING_DIM, EMBEDDING_MODEL

_REMOTE: dict[str, Any] = {}
_remote_ready = False


def ensure_remote_defaults() -> None:
    """Lazily populate `_REMOTE` with schema-derived defaults and env fallbacks (once).

    Safe to call repeatedly; subsequent calls are no-ops once initialized.
    """
    global _remote_ready
    if _remote_ready:
        return
    from app.config.defaults import apply_env_fallbacks, build_settings_defaults, load_schema

    schema = load_schema()
    _REMOTE.update(build_settings_defaults(schema))
    apply_env_fallbacks(_REMOTE, schema)
    _remote_ready = True


def set_remote(name: str, value: Any) -> None:
    """Set a single remote-config-backed setting value.

    Args:
        name: Settings attribute name.
        value: Value to store.
    """
    ensure_remote_defaults()
    _REMOTE[name] = value


def update_remote(values: dict[str, Any]) -> None:
    """Bulk-update remote-config-backed setting values.

    Args:
        values: Mapping of settings attribute name to new value.
    """
    ensure_remote_defaults()
    _REMOTE.update(values)


def get_remote(name: str, default: Any = None) -> Any:
    """Read a remote-config-backed setting value.

    Args:
        name: Settings attribute name.
        default: Value to return if the setting isn't present.

    Returns:
        Any: The stored value, or `default` if not set.
    """
    ensure_remote_defaults()
    return _REMOTE.get(name, default)


def __getattr__(name: str) -> Any:
    """Module-level attribute fallback: resolve names not defined at import time
    from the remote-config store (`_REMOTE`).

    Args:
        name: Attribute name being accessed on this module.

    Returns:
        Any: The value from `_REMOTE`.

    Raises:
        AttributeError: If `name` starts with "_" or isn't present in `_REMOTE`.
    """
    if name.startswith("_"):
        raise AttributeError(name)
    ensure_remote_defaults()
    if name in _REMOTE:
        return _REMOTE[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
