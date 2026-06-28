"""Biến môi trường — infra từ .env; OpenAI/agent/prompt từ Supabase `config` (remote.py)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(override=True)


def _env_str(key: str) -> str:
    return os.getenv(key, "").strip()


def _env_int(key: str) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ↓ override bởi Supabase config khi startup
OPENAI_API_KEY: str = _env_str("OPENAI_API_KEY")
OPENAI_MODEL: str = _env_str("OPENAI_MODEL")
OPENAI_TOOL_MODEL: str = _env_str("OPENAI_TOOL_MODEL")
OPENAI_MAX_TOKENS: int = _env_int("OPENAI_MAX_TOKENS")
OPENAI_TOOL_MAX_TOKENS: int = _env_int("OPENAI_TOOL_MAX_TOKENS")

# DeepSeek
DEEP_SEEK_API_KEY: str = _env_str("DEEP_SEEK_API_KEY")
DEEP_SEEK_MODEL: str = _env_str("DEEP_SEEK_MODEL")
DEEP_SEEK_TOOL_MODEL: str = _env_str("DEEP_SEEK_TOOL_MODEL")

DATA_MINER_URL: str = os.getenv("DATA_MINER_URL", "http://localhost:8000")
DATA_MINER_KEY: str = _env_str("DATA_MINER_KEY")
DATA_MINER_TIMEOUT: int = int(os.getenv("DATA_MINER_TIMEOUT", "60"))

API_KEYS: list[str] = [
    key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()
]

CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

AGENT_SYSTEM: str = ""
AGENT_MAX_ITER: int = _env_int("AGENT_MAX_ITER")
AGENT_MAX_RESULT_CHARS: int = _env_int("AGENT_MAX_RESULT_CHARS")
AGENT_MAX_COMMENTS: int = _env_int("AGENT_MAX_COMMENTS")
AGENT_MAX_COMMENT_LEN: int = _env_int("AGENT_MAX_COMMENT_LEN")
AGENT_MAX_LIST_ITEMS: int = _env_int("AGENT_MAX_LIST_ITEMS")

AGENT_RATE_LIMIT: str = _env_str("AGENT_RATE_LIMIT")
QR_RATE_LIMIT: str = _env_str("QR_RATE_LIMIT")
SHORTEN_RATE_LIMIT: str = _env_str("SHORTEN_RATE_LIMIT")
YOUTUBE_RATE_LIMIT: str = _env_str("YOUTUBE_RATE_LIMIT")

GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "")
GEOIP_CACHE_TTL: int = int(os.getenv("GEOIP_CACHE_TTL", "3600"))
GEOIP_CACHE_MAX: int = int(os.getenv("GEOIP_CACHE_MAX", "500"))

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
REMOTE_CONFIG_TTL: int = int(
    os.getenv("REMOTE_CONFIG_TTL", "5")
)  # phút — refresh Supabase config

RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "")
RABBITMQ_EXCHANGE: str = os.getenv("RABBITMQ_EXCHANGE", "knowledge.ingest")
INGEST_ENABLED: bool = os.getenv("INGEST_ENABLED", "true").lower() == "true"
INGEST_WORKER_INLINE: bool = os.getenv("INGEST_WORKER_INLINE", "true").lower() == "true"
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))
CURATED_TOP_N: int = int(os.getenv("CURATED_TOP_N", "300"))

RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "true").lower() == "true"
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "8"))
RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.65"))
CACHE_TTL_DAYS: int = int(os.getenv("CACHE_TTL_DAYS", "7"))
