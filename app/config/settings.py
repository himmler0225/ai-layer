from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ── App ───────────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Claude ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))

# ── Downstream services ───────────────────────────────────────────────────────
DATA_MINER_URL: str  = os.getenv("DATA_MINER_URL", "http://localhost:8000")
DATA_MINER_KEY: str  = os.getenv("DATA_MINER_KEY", "")
YOUTUBE_API_URL: str = os.getenv("YOUTUBE_API_URL", "http://localhost:3000")
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

# ── Auth ──────────────────────────────────────────────────────────────────────
API_KEYS: list[str] = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

# ── GeoIP ─────────────────────────────────────────────────────────────────────
# Path to GeoLite2-City.mmdb (optional — falls back to ip-api.com if not set)
# Download free: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "")
GEOIP_CACHE_TTL: int = int(os.getenv("GEOIP_CACHE_TTL", "3600"))  # seconds
GEOIP_CACHE_MAX: int = int(os.getenv("GEOIP_CACHE_MAX", "500"))   # max cached IPs
