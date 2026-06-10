import importlib
from app.config.logger import Logger
import time
from typing import Dict, Optional

import httpx
from fastapi import Request

from app.config.settings import GEOIP_DB_PATH, GEOIP_CACHE_TTL, GEOIP_CACHE_MAX

logger = Logger.get(__name__)

# ── Local database (optional) ─────────────────────────────────────────────────

_reader = None

if GEOIP_DB_PATH:
    try:
        geoip2_db = importlib.import_module("geoip2.database")
        _reader = geoip2_db.Reader(GEOIP_DB_PATH)
        logger.info("GeoIP database loaded: %s", GEOIP_DB_PATH)
    except Exception as e:
        logger.warning("GeoIP database failed to load: %s", e)

# ── Cache ─────────────────────────────────────────────────────────────────────

_cache: Dict[str, Dict] = {}


def _from_cache(ip: str) -> Optional[Dict]:
    entry = _cache.get(ip)
    if entry and time.time() - entry["ts"] < GEOIP_CACHE_TTL:
        return entry["data"]
    return None


def _to_cache(ip: str, data: Dict) -> None:
    _cache[ip] = {"data": data, "ts": time.time()}
    if len(_cache) > GEOIP_CACHE_MAX:
        oldest = sorted(_cache, key=lambda k: _cache[k]["ts"])[:100]
        for k in oldest:
            del _cache[k]


# ── IP extraction ─────────────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


# ── Lookups ───────────────────────────────────────────────────────────────────

def _local_lookup(ip: str) -> Optional[Dict]:
    if not _reader:
        return None
    try:
        r = _reader.city(ip)
        return {
            "ip":           ip,
            "country":      r.country.name,
            "country_code": r.country.iso_code,
            "region":       r.subdivisions.most_specific.name,
            "city":         r.city.name,
            "latitude":     r.location.latitude,
            "longitude":    r.location.longitude,
            "timezone":     r.location.time_zone,
            "source":       "local",
        }
    except Exception:
        return None


async def _api_lookup(ip: str) -> Dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,regionName,city,lat,lon,timezone,isp,org"},
            )
            data = r.json()
            if data.get("status") == "success":
                return {
                    "ip":           ip,
                    "country":      data.get("country"),
                    "country_code": data.get("countryCode"),
                    "region":       data.get("regionName"),
                    "city":         data.get("city"),
                    "latitude":     data.get("lat"),
                    "longitude":    data.get("lon"),
                    "timezone":     data.get("timezone"),
                    "isp":          data.get("isp"),
                    "org":          data.get("org"),
                    "source":       "api",
                }
    except Exception as e:
        logger.debug("GeoIP API lookup failed for %s: %s", ip, e)
    return {"ip": ip, "source": "unknown"}


async def get_geo_info(ip: str) -> Dict:
    if ip in ("127.0.0.1", "::1", "unknown"):
        return {"ip": ip, "country": "Localhost", "source": "local"}

    cached = _from_cache(ip)
    if cached:
        return cached

    result = _local_lookup(ip) or await _api_lookup(ip)
    _to_cache(ip, result)
    return result
