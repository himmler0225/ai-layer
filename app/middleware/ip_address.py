from __future__ import annotations

"""Lấy IP client và tra GeoIP."""

import importlib
import re
import time
from typing import Dict, Optional

import httpx
from fastapi import Request

from app.config.constants import GEOIP_LOOKUP_TIMEOUT
from app.config.logger import Logger
from app.config.settings import GEOIP_CACHE_MAX, GEOIP_CACHE_TTL, GEOIP_DB_PATH

logger = Logger.get(__name__)

_IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_IPV6 = re.compile(r"^[0-9a-fA-F:]+$")


def _is_valid_ip(ip: str) -> bool:
    """Kiểm tra chuỗi có phải IPv4/IPv6 hợp lệ."""
    if _IPV4.match(ip):
        return all(0 <= int(p) <= 255 for p in ip.split("."))
    return bool(_IPV6.match(ip) and 2 <= ip.count(":") <= 7)


_reader = None

if GEOIP_DB_PATH:
    try:
        geoip2_db = importlib.import_module("geoip2.database")
        _reader = geoip2_db.Reader(GEOIP_DB_PATH)
        logger.info("[geoip] database loaded path=%s", GEOIP_DB_PATH)
    except Exception as e:
        logger.warning("[geoip] database load failed: %s", e)

_cache: Dict[str, Dict] = {}


def _from_cache(ip: str) -> Optional[Dict]:
    """Đọc kết quả GeoIP từ cache RAM."""
    entry = _cache.get(ip)
    if entry and time.time() - entry["ts"] < GEOIP_CACHE_TTL:
        return entry["data"]
    return None


def _to_cache(ip: str, data: Dict) -> None:
    """Ghi kết quả GeoIP vào cache RAM."""
    _cache[ip] = {"data": data, "ts": time.time()}
    if len(_cache) > GEOIP_CACHE_MAX:
        oldest = sorted(_cache, key=lambda k: _cache[k]["ts"])[:100]
        for k in oldest:
            del _cache[k]


_http: Optional[httpx.AsyncClient] = None


def _get_http() -> httpx.AsyncClient:
    """Http client dùng chung cho rút gọn URL."""
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=GEOIP_LOOKUP_TIMEOUT)
    return _http


def get_client_ip(request: Request) -> str:
    """Lấy IP thật của client (ưu tiên X-Forwarded-For)."""
    for header in ("X-Forwarded-For", "X-Real-IP"):
        raw = request.headers.get(header)
        if not raw:
            continue
        candidate = raw.split(",")[0].strip()
        if _is_valid_ip(candidate):
            return candidate
        logger.debug("Ignored invalid IP in %s: %r", header, candidate)
    return request.client.host if request.client else "unknown"


def _local_lookup(ip: str) -> Optional[Dict]:
    """Tra GeoIP bằng file MaxMind local."""
    if not _reader:
        return None
    try:
        r = _reader.city(ip)
        return {
            "ip": ip,
            "country": r.country.name,
            "country_code": r.country.iso_code,
            "region": r.subdivisions.most_specific.name,
            "city": r.city.name,
            "latitude": r.location.latitude,
            "longitude": r.location.longitude,
            "timezone": r.location.time_zone,
            "source": "local",
        }
    except Exception:
        return None


async def _api_lookup(ip: str) -> Dict:
    """Tra GeoIP qua ip-api.com khi không có file local."""
    try:
        r = await _get_http().get(
            f"http://ip-api.com/json/{ip}",
            params={
                "fields": "status,country,countryCode,regionName,city,lat,lon,timezone,isp,org"
            },
        )
        data = r.json()
        if data.get("status") == "success":
            return {
                "ip": ip,
                "country": data.get("country"),
                "country_code": data.get("countryCode"),
                "region": data.get("regionName"),
                "city": data.get("city"),
                "latitude": data.get("lat"),
                "longitude": data.get("lon"),
                "timezone": data.get("timezone"),
                "isp": data.get("isp"),
                "org": data.get("org"),
                "source": "api",
            }
    except Exception as e:
        logger.warning("[geoip] api lookup failed ip=%s error=%s", ip, exc)
    return {"ip": ip, "source": "unknown"}


async def get_geo_info(ip: str) -> Dict:
    """Tra vị trí địa lý từ IP (cache → local → API)."""
    if ip in ("127.0.0.1", "::1", "unknown"):
        return {"ip": ip, "country": "Localhost", "source": "local"}
    cached = _from_cache(ip)
    if cached:
        return cached
    result = _local_lookup(ip) or await _api_lookup(ip)
    _to_cache(ip, result)
    return result
