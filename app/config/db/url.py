"""DATABASE_URL helpers — async SQLAlchemy + Supabase Postgres (SSL)."""

import ssl
from uuid import uuid4
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def _unique_statement_name() -> str:
    """Unique prepared-statement names so pgbouncer (transaction mode) never collides."""
    return f"__asyncpg_{uuid4().hex}__"


def normalize_async_database_url(url: str) -> str:
    """Rewrite a plain postgres/postgresql URL to use the asyncpg driver.

    Args:
        url: Database URL, potentially using the `postgres://` or `postgresql://` scheme.

    Returns:
        str: The URL with scheme `postgresql+asyncpg://` if it matched, otherwise unchanged.
    """
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
    """Derive asyncpg connect_args (SSL context, pgbouncer workarounds) from a database URL.

    Args:
        url: Database URL to inspect (scheme, host, port, and query string).

    Returns:
        dict: Extra keyword arguments for `create_async_engine`/asyncpg, covering
        SSL context setup and pgbouncer-safe prepared statement handling.
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    sslmode = (query.get("sslmode") or [None])[0]
    host = (parsed.hostname or "").lower()
    port = parsed.port
    is_supabase = "supabase.com" in host
    # Supabase pooler (6543) runs pgbouncer in transaction mode → asyncpg prepared
    # statements clash ("__asyncpg_stmt_N__ already exists"). Disable statement cache
    # and use unique statement names to stay compatible.
    is_pgbouncer = is_supabase and (port == 6543 or "pgbouncer" in query)
    args: dict = {}
    if is_pgbouncer:
        args["statement_cache_size"] = 0
        args["prepared_statement_name_func"] = _unique_statement_name

    needs_ssl = sslmode in ("require", "verify-full", "verify-ca") or is_supabase
    if not needs_ssl:
        return args
    ctx = ssl.create_default_context()
    # Supabase pooler / sslmode=require: encrypt without strict CA verify (avoids
    # CERTIFICATE_VERIFY_FAILED on macOS/Python when chain includes pooler certs).
    if sslmode in (None, "require") or is_supabase:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    args["ssl"] = ctx
    return args


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

