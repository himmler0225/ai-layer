"""Request locale resolution — driven by I18N_* settings and X-Lang header."""

from __future__ import annotations

from contextvars import ContextVar

from starlette.requests import Request

# Defaults; overridden at import from settings when available.
_DEFAULT_SUPPORTED = ("vi", "en")
_DEFAULT_LOCALE = "en"

# Common BCP-47 prefix → canonical code (extend as you add catalogs).
_LOCALE_ALIASES: dict[str, str] = {
    "vi": "vi",
    "en": "en",
    "ja": "ja",
    "jp": "ja",
    "zh": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
    "ko": "ko",
    "kr": "ko",
    "th": "th",
    "fr": "fr",
    "id": "id",
    "in": "id",
    "ms": "ms",
    "de": "de",
    "es": "es",
    "pt": "pt",
    "ru": "ru",
    "hi": "hi",
}


def _load_supported() -> tuple[frozenset[str], str]:
    try:
        from app.config import settings as settings

        raw = getattr(settings, "I18N_SUPPORTED_LOCALES", None)
        default = getattr(settings, "I18N_DEFAULT_LOCALE", _DEFAULT_LOCALE)
        if isinstance(raw, str):
            codes = [c.strip().lower() for c in raw.split(",") if c.strip()]
        elif isinstance(raw, (list, tuple, set, frozenset)):
            codes = [str(c).strip().lower() for c in raw if str(c).strip()]
        else:
            codes = list(_DEFAULT_SUPPORTED)
        if not codes:
            codes = list(_DEFAULT_SUPPORTED)
        default_loc = str(default or _DEFAULT_LOCALE).strip().lower() or _DEFAULT_LOCALE
        if default_loc not in codes:
            codes = [default_loc, *codes]
        return frozenset(codes), default_loc
    except Exception:
        return frozenset(_DEFAULT_SUPPORTED), _DEFAULT_LOCALE


SUPPORTED, DEFAULT_LOCALE = _load_supported()

_locale_ctx: ContextVar[str] = ContextVar("locale", default=DEFAULT_LOCALE)


def reload_locale_config() -> None:
    """Re-read SUPPORTED / DEFAULT from settings (tests / hot config)."""
    global SUPPORTED, DEFAULT_LOCALE
    SUPPORTED, DEFAULT_LOCALE = _load_supported()
    _locale_ctx.set(DEFAULT_LOCALE)


def get_locale() -> str:
    return _locale_ctx.get()


def set_locale(locale: str) -> None:
    _locale_ctx.set(normalize_locale(locale))


def canonicalize(value: str) -> str:
    """Map raw tag (e.g. vi-VN, zh-Hans) to a short code."""
    raw = value.strip().lower().replace("_", "-")
    if not raw:
        return DEFAULT_LOCALE
    if raw in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[raw]
    primary = raw.split("-", 1)[0]
    if primary in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[primary]
    return primary


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    code = canonicalize(value)
    if code in SUPPORTED:
        return code
    # Prefer a supported prefix match (e.g. request "en-GB" with SUPPORTED={en,vi}).
    for supported in SUPPORTED:
        if code.startswith(supported) or supported.startswith(code):
            return supported
    return DEFAULT_LOCALE


def resolve_locale(request: Request) -> str:
    """Prefer X-Lang, then X-Locale, then Accept-Language."""
    for header in (
        "x-lang",
        "X-Lang",
        "x-locale",
        "X-Locale",
    ):
        value = request.headers.get(header)
        if value:
            return normalize_locale(value)

    accept = request.headers.get("accept-language", "")
    for part in accept.split(","):
        token = part.split(";")[0].strip()
        if not token:
            continue
        loc = normalize_locale(token)
        if loc in SUPPORTED:
            return loc
    return DEFAULT_LOCALE
