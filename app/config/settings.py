from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv(override=True)

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Claude — sourced from Supabase remote config (config/remote.py), not from env.
ANTHROPIC_API_KEY: str = ""
CLAUDE_MODEL:           str = ""   # required — set via Supabase remote config
CLAUDE_TOOL_MODEL:      str = ""   # optional — Haiku for tool calls
CLAUDE_MAX_TOKENS:      int = 4096 # Opus synthesis output budget
CLAUDE_TOOL_MAX_TOKENS: int = 2048 # Haiku tool-call output budget

DATA_MINER_URL:     str = os.getenv("DATA_MINER_URL",     "http://localhost:8000")
DATA_MINER_KEY:     str = ""  # Supabase remote config
DATA_MINER_TIMEOUT: int = int(os.getenv("DATA_MINER_TIMEOUT", "60"))

API_KEYS: list[str] = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
CORS_ORIGINS: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

# Agent limits — sourced from Supabase remote config (config/remote.py), not from env.
AGENT_MAX_ITER:         int = 10
AGENT_MAX_RESULT_CHARS: int = 8000
AGENT_MAX_COMMENTS:     int = 200
AGENT_MAX_COMMENT_LEN:  int = 150
AGENT_MAX_LIST_ITEMS:   int = 15

GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "")
GEOIP_CACHE_TTL: int = int(os.getenv("GEOIP_CACHE_TTL", "3600"))  # seconds
GEOIP_CACHE_MAX: int = int(os.getenv("GEOIP_CACHE_MAX", "500"))   # max cached IPs

# PostgreSQL
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/youtube")

# Redis
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB:   int = int(os.getenv("REDIS_DB",   "1"))

# Supabase — JWT verification + remote config
SUPABASE_URL:         str = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY:    str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# Cache TTLs (seconds)
SUPABASE_TOKEN_TTL:   int = 3600   # JWT auth cache (1 h)
HISTORY_SESSIONS_TTL: int = 300    # sessions list cache (5 min)
HISTORY_MESSAGES_TTL: int = 600    # messages cache (10 min)
REMOTE_CONFIG_TTL:    int = 5      # timeout for fetching remote config

# MongoDB
MONGODB_URL: str = os.getenv("MONGODB_URL", "")
MONGODB_NAME: str = os.getenv("MONGODB_NAME", "")