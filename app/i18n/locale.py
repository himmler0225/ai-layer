"""Resolve request locale (vi | en) for user-facing API messages."""

from contextvars import ContextVar

from starlette.requests import Request

SUPPORTED = frozenset({"vi", "en"})
DEFAULT_LOCALE = "en"

_locale_ctx: ContextVar[str] = ContextVar("locale", default=DEFAULT_LOCALE)


def get_locale() -> str:
    return _locale_ctx.get()


def set_locale(locale: str) -> None:
    _locale_ctx.set(normalize_locale(locale))


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    raw = value.strip().lower()
    if raw in SUPPORTED:
        return raw
    if raw.startswith("vi"):
        return "vi"
    if raw.startswith("en"):
        return "en"
    return DEFAULT_LOCALE


def resolve_locale(request: Request) -> str:
    header = request.headers.get("x-locale") or request.headers.get("X-Locale")
    if header:
        return normalize_locale(header)
    accept = request.headers.get("accept-language", "")
    for part in accept.split(","):
        token = part.split(";")[0].strip()
        if token:
            loc = normalize_locale(token)
            if loc in SUPPORTED:
                return loc
    return DEFAULT_LOCALE
