import importlib
import re
import time
import httpx
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.config.constants import GEOIP_LOOKUP_TIMEOUT
from app.config.logger import Logger, log_event
from app.config.settings import GEOIP_CACHE_MAX, GEOIP_CACHE_TTL, GEOIP_DB_PATH

logger = Logger.get(__name__)
_IPV4 = re.compile("^(\\d{1,3}\\.){3}\\d{1,3}$")
_IPV6 = re.compile("^[0-9a-fA-F:]+$")


def _is_valid_ip(ip: str) -> bool:
    """Check whether a string looks like a valid IPv4 or IPv6 address.

    Args:
        ip: Candidate address string.

    Returns:
        `True` if it matches IPv4 dotted-quad format with each octet in
        0-255, or a plausible IPv6 pattern (hex groups/colons, 2-7 colons)."""
    if _IPV4.match(ip):
        return all(0 <= int(p) <= 255 for p in ip.split("."))
    return bool(_IPV6.match(ip) and 2 <= ip.count(":") <= 7)


_reader = None
if GEOIP_DB_PATH:
    try:
        geoip2_db = importlib.import_module("geoip2.database")
        _reader = geoip2_db.Reader(GEOIP_DB_PATH)
        logger.info(log_event("geoip", "database loaded", path=GEOIP_DB_PATH))
    except Exception as e:
        logger.warning(log_event("geoip", "database load failed", error=e))
_cache: dict[str, dict] = {}


def _from_cache(ip: str) -> dict | None:
    """Look up a cached geo-info result for an IP if it hasn't expired.

    Args:
        ip: The IP address to look up.

    Returns:
        The cached geo-info dict, or `None` if missing or older than
        `GEOIP_CACHE_TTL` seconds."""
    entry = _cache.get(ip)
    if entry and time.time() - entry["ts"] < GEOIP_CACHE_TTL:
        return entry["data"]
    return None


def _to_cache(ip: str, data: dict) -> None:
    """Store a geo-info result in the in-memory cache, evicting old entries if full.

    Args:
        ip: The IP address the result is for.
        data: The geo-info dict to cache.

    Returns:
        None."""
    _cache[ip] = {"data": data, "ts": time.time()}
    if len(_cache) > GEOIP_CACHE_MAX:
        oldest = sorted(_cache, key=lambda k: _cache[k]["ts"])[:100]
        for k in oldest:
            del _cache[k]


_http: httpx.AsyncClient | None = None


def _get_http() -> httpx.AsyncClient:
    """Get or lazily (re)create the shared HTTP client used for IP-API lookups.

    Returns:
        The shared `httpx.AsyncClient` instance."""
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=GEOIP_LOOKUP_TIMEOUT)
    return _http


def get_client_ip(request: Request) -> str:
    """Determine the originating client IP for a request.

    Checks `X-Forwarded-For` then `X-Real-IP` headers for a valid IP address
    (taking the first entry of a comma-separated list), falling back to the
    direct connection's peer address.

    Args:
        request: The incoming FastAPI/Starlette request.

    Returns:
        The resolved client IP, or `"unknown"` if none could be determined."""
    for header in ("X-Forwarded-For", "X-Real-IP"):
        raw = request.headers.get(header)
        if not raw:
            continue
        candidate = raw.split(",")[0].strip()
        if _is_valid_ip(candidate):
            return candidate
        logger.debug(log_event("geoip", "invalid ip ignored", header=header, value=candidate))
    return request.client.host if request.client else "unknown"


def _local_lookup(ip: str) -> dict | None:
    """Look up geo-info for an IP using the local GeoIP2 database, if loaded.

    Args:
        ip: The IP address to look up.

    Returns:
        A dict with country/region/city/coordinates/timezone and
        `source: "local"`, or `None` if no local reader is available or the
        lookup fails (e.g. IP not found in the database)."""
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


async def _api_lookup(ip: str) -> dict:
    """Look up geo-info for an IP via the ip-api.com HTTP API.

    Args:
        ip: The IP address to look up.

    Returns:
        A dict with country/region/city/coordinates/timezone/isp/org and
        `source: "api"` on success; `{"ip": ip, "source": "unknown"}` if the
        API call fails or reports a non-success status."""
    try:
        r = await _get_http().get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,countryCode,regionName,city,lat,lon,timezone,isp,org"},
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
        logger.warning(log_event("geoip", "api lookup failed", ip=ip, error=e))
    return {"ip": ip, "source": "unknown"}


async def get_geo_info(ip: str) -> dict:
    """Resolve geo-location info for an IP, using cache, then local DB, then API.

    Args:
        ip: The IP address to resolve. Loopback addresses short-circuit to a
            `"Localhost"` result.

    Returns:
        A geo-info dict (see `_local_lookup`/`_api_lookup`), served from cache
        when available and freshly cached otherwise."""
    if ip in ("127.0.0.1", "::1", "unknown"):
        return {"ip": ip, "country": "Localhost", "source": "local"}
    cached = _from_cache(ip)
    if cached:
        return cached
    result = _local_lookup(ip) or await _api_lookup(ip)
    _to_cache(ip, result)
    return result


class GeoIPMiddleware(BaseHTTPMiddleware):
    """Middleware that resolves the client IP and geo-location for each
    request and attaches them to `request.state` as `client_ip`/`geo_info`."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Resolve and attach client IP/geo info, then continue the request.

        Args:
            request: The incoming request.
            call_next: The next handler in the middleware chain.

        Returns:
            The downstream response."""
        ip = get_client_ip(request)
        request.state.client_ip = ip
        request.state.geo_info = await get_geo_info(ip)
        return await call_next(request)
