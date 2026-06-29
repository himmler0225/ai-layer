from __future__ import annotations
import importlib
import re
import time
from typing import Dict, Optional
import httpx
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.config.constants import GEOIP_LOOKUP_TIMEOUT
from app.config.logger import Logger
from app.config.settings import GEOIP_CACHE_MAX, GEOIP_CACHE_TTL, GEOIP_DB_PATH
logger = Logger.get(__name__)
_IPV4 = re.compile('^(\\d{1,3}\\.){3}\\d{1,3}$')
_IPV6 = re.compile('^[0-9a-fA-F:]+$')

def _is_valid_ip(ip: str) -> bool:
    """(Nội bộ) Is valid ip.

    Args:
        ip: (str) Tham số `ip`.

    Returns:
        (bool) Kết quả trả về."""
    if _IPV4.match(ip):
        return all((0 <= int(p) <= 255 for p in ip.split('.')))
    return bool(_IPV6.match(ip) and 2 <= ip.count(':') <= 7)
_reader = None
if GEOIP_DB_PATH:
    try:
        geoip2_db = importlib.import_module('geoip2.database')
        _reader = geoip2_db.Reader(GEOIP_DB_PATH)
        logger.info('[geoip] database loaded path=%s', GEOIP_DB_PATH)
    except Exception as e:
        logger.warning('[geoip] database load failed: %s', e)
_cache: Dict[str, Dict] = {}

def _from_cache(ip: str) -> Optional[Dict]:
    """(Nội bộ) From cache.

    Args:
        ip: (str) Tham số `ip`.

    Returns:
        (Optional[Dict]) Kết quả trả về."""
    entry = _cache.get(ip)
    if entry and time.time() - entry['ts'] < GEOIP_CACHE_TTL:
        return entry['data']
    return None

def _to_cache(ip: str, data: Dict) -> None:
    """(Nội bộ) To cache.

    Args:
        ip: (str) Tham số `ip`.
        data: (Dict) Tham số `data`.

    Returns:
        (None) Kết quả trả về."""
    _cache[ip] = {'data': data, 'ts': time.time()}
    if len(_cache) > GEOIP_CACHE_MAX:
        oldest = sorted(_cache, key=lambda k: _cache[k]['ts'])[:100]
        for k in oldest:
            del _cache[k]
_http: Optional[httpx.AsyncClient] = None

def _get_http() -> httpx.AsyncClient:
    """(Nội bộ) Lấy http.

    Returns:
        (httpx.AsyncClient) Kết quả trả về."""
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=GEOIP_LOOKUP_TIMEOUT)
    return _http

def get_client_ip(request: Request) -> str:
    """Lấy client ip.

    Args:
        request: (Request) Tham số `request`.

    Returns:
        (str) Kết quả trả về."""
    for header in ('X-Forwarded-For', 'X-Real-IP'):
        raw = request.headers.get(header)
        if not raw:
            continue
        candidate = raw.split(',')[0].strip()
        if _is_valid_ip(candidate):
            return candidate
        logger.debug('Ignored invalid IP in %s: %r', header, candidate)
    return request.client.host if request.client else 'unknown'

def _local_lookup(ip: str) -> Optional[Dict]:
    """(Nội bộ) Local lookup.

    Args:
        ip: (str) Tham số `ip`.

    Returns:
        (Optional[Dict]) Kết quả trả về."""
    if not _reader:
        return None
    try:
        r = _reader.city(ip)
        return {'ip': ip, 'country': r.country.name, 'country_code': r.country.iso_code, 'region': r.subdivisions.most_specific.name, 'city': r.city.name, 'latitude': r.location.latitude, 'longitude': r.location.longitude, 'timezone': r.location.time_zone, 'source': 'local'}
    except Exception:
        return None

async def _api_lookup(ip: str) -> Dict:
    """(Nội bộ) Api lookup (async).

    Args:
        ip: (str) Tham số `ip`.

    Returns:
        (Dict) Kết quả trả về."""
    try:
        r = await _get_http().get(f'http://ip-api.com/json/{ip}', params={'fields': 'status,country,countryCode,regionName,city,lat,lon,timezone,isp,org'})
        data = r.json()
        if data.get('status') == 'success':
            return {'ip': ip, 'country': data.get('country'), 'country_code': data.get('countryCode'), 'region': data.get('regionName'), 'city': data.get('city'), 'latitude': data.get('lat'), 'longitude': data.get('lon'), 'timezone': data.get('timezone'), 'isp': data.get('isp'), 'org': data.get('org'), 'source': 'api'}
    except Exception as e:
        logger.warning('[geoip] api lookup failed ip=%s error=%s', ip, e)
    return {'ip': ip, 'source': 'unknown'}

async def get_geo_info(ip: str) -> Dict:
    """Lấy geo info (async).

    Args:
        ip: (str) Tham số `ip`.

    Returns:
        (Dict) Kết quả trả về."""
    if ip in ('127.0.0.1', '::1', 'unknown'):
        return {'ip': ip, 'country': 'Localhost', 'source': 'local'}
    cached = _from_cache(ip)
    if cached:
        return cached
    result = _local_lookup(ip) or await _api_lookup(ip)
    _to_cache(ip, result)
    return result


class GeoIPMiddleware(BaseHTTPMiddleware):
    """    Lớp `GeoIPMiddleware` (kế thừa BaseHTTPMiddleware)."""
    async def dispatch(self, request: Request, call_next) -> Response:
        """Dispatch `dispatch` (async).

    Args:
        request: (Request) Tham số `request`.
        call_next: (Any) Tham số `call_next`.

    Returns:
        (Response) Kết quả trả về."""
        ip = get_client_ip(request)
        request.state.client_ip = ip
        request.state.geo_info = await get_geo_info(ip)
        return await call_next(request)
