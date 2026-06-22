from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv(override=True)

# =========================
# CORE
# =========================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_TOOL_MODEL: str = os.getenv("OPENAI_TOOL_MODEL", "gpt-4o-mini")

OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "4096"))
OPENAI_TOOL_MAX_TOKENS: int = int(os.getenv("OPENAI_TOOL_MAX_TOKENS", "2048"))

# =========================
# DATA MINER
# =========================
DATA_MINER_URL: str = os.getenv("DATA_MINER_URL", "http://localhost:8000")
DATA_MINER_KEY: str = os.getenv("DATA_MINER_KEY", "")
DATA_MINER_TIMEOUT: int = int(os.getenv("DATA_MINER_TIMEOUT", "60"))

# =========================
# API / SECURITY
# =========================
API_KEYS: list[str] = [
    k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()
]

CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

# =========================
# AGENT CORE
# =========================
AGENT_SYSTEM: str = ""

AGENT_MAX_ITER: int = 10
AGENT_MAX_RESULT_CHARS: int = 8000
AGENT_MAX_COMMENTS: int = 200
AGENT_MAX_COMMENT_LEN: int = 150
AGENT_MAX_LIST_ITEMS: int = 15

# =========================
# GEOIP
# =========================
GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "")
GEOIP_CACHE_TTL: int = int(os.getenv("GEOIP_CACHE_TTL", "3600"))
GEOIP_CACHE_MAX: int = int(os.getenv("GEOIP_CACHE_MAX", "500"))

# =========================
# DATABASE
# =========================
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/youtube"
)

REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "1"))

MONGODB_URL: str = os.getenv("MONGODB_URL", "")
MONGODB_NAME: str = os.getenv("MONGODB_NAME", "")

# =========================
# SUPABASE
# =========================
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# =========================
# CACHE TTL
# =========================
SUPABASE_TOKEN_TTL: int = 3600
HISTORY_SESSIONS_TTL: int = 300
HISTORY_MESSAGES_TTL: int = 600
REMOTE_CONFIG_TTL: int = 5
