"""Bootstrap config.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _env_list(key: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(key, default).split(",") if item.strip()]


LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

API_KEYS: list[str] = _env_list("API_KEYS")
CORS_ORIGINS: list[str] = _env_list("CORS_ORIGINS", "http://localhost:3000")

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/youtube",
)

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

_REMOTE_DEFAULTS: dict[str, Any] = {
    # Supabase `AI_MODELS`
    "OPENAI_API_KEY": "",
    "OPENAI_MODEL": "",
    "OPENAI_TOOL_MODEL": "",
    "OPENAI_MAX_TOKENS": 0,
    "OPENAI_TOOL_MAX_TOKENS": 0,
    "DEEP_SEEK_API_KEY": "",
    "DEEP_SEEK_MODEL": "",
    "DEEP_SEEK_TOOL_MODEL": "",
    # Supabase `PROMPTS`
    "AGENT_SYSTEM": "",
    # Supabase `AI_AGENT`
    "AGENT_MAX_ITER": 0,
    "AGENT_MAX_RESULT_CHARS": 0,
    "AGENT_MAX_COMMENTS": 0,
    "AGENT_MAX_COMMENT_LEN": 0,
    "AGENT_MAX_LIST_ITEMS": 0,
    # Supabase `RATE_LIMIT`
    "AGENT_RATE_LIMIT": "",
    "QR_RATE_LIMIT": "",
    "SHORTEN_RATE_LIMIT": "",
    "YOUTUBE_RATE_LIMIT": "",
    # Supabase `SERVICES`
    "DATA_MINER_URL": "",
    "DATA_MINER_KEY": "",
    "DATA_MINER_TIMEOUT": 0,
    "RABBITMQ_URL": "",
    "RABBITMQ_EXCHANGE": "",
    "INGEST_ENABLED": False,
    "INGEST_WORKER_INLINE": False,
    "EMBEDDING_MODEL": "",
    "EMBEDDING_DIM": 0,
    "CURATED_TOP_N": 0,
    "RAG_ENABLED": False,
    "RAG_TOP_K": 0,
    "RAG_MIN_SCORE": 0.0,
    "CACHE_TTL_DAYS": 0,
}


def __getattr__(name: str) -> Any:
    try:
        return _REMOTE_DEFAULTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
