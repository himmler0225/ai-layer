"""DATABASE_URL helpers — async SQLAlchemy + Supabase Postgres (SSL)."""

import ssl
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_async_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def strip_unsupported_query_params(url: str) -> str:
    """Drop params handled in connect_args (asyncpg does not parse sslmode in URL)."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("sslmode", "supabase"):
        query.pop(key, None)
    flat = {k: v[0] for k, v in query.items() if v}
    return urlunparse(parsed._replace(query=urlencode(flat)))


def database_connect_args(url: str) -> dict:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    sslmode = (query.get("sslmode") or [None])[0]
    host = (parsed.hostname or "").lower()
    needs_ssl = sslmode in ("require", "verify-full", "verify-ca") or "supabase.co" in host
    if not needs_ssl:
        return {}
    ctx = ssl.create_default_context()
    if sslmode == "require":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return {"ssl": ctx}


def resolve_database_url(url: str) -> tuple[str, dict]:
    """Return (async_engine_url, connect_args) for SQLAlchemy create_async_engine."""
    async_url = strip_unsupported_query_params(normalize_async_database_url(url))
    return async_url, database_connect_args(url)


def database_url_label(url: str) -> str:
    """Safe connection label for logs (no password)."""
    parsed = urlparse(url)
    host = parsed.hostname or "?"
    port = parsed.port or 5432
    db = (parsed.path or "/").lstrip("/") or "postgres"
    user = parsed.username or "?"
    ssl = "yes" if database_connect_args(url) else "no"
    return f"{user}@{host}:{port}/{db} ssl={ssl}"

