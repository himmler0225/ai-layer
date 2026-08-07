"""Translate message keys for the request locale (X-Lang).

Catalogs live in `app/i18n/locales/<code>.py` — one dict per language.
Lookup: current locale → en → any available catalog.
"""

from typing import Any

from app.i18n.locales import CATALOGS, MESSAGE_KEYS

Locale = str


def t(key: str, locale: Locale | None = None, **params: Any) -> str:
    """Translate message key for locale (falls back to en, then any available)."""
    from app.i18n.locale import DEFAULT_LOCALE, get_locale

    loc = locale or get_locale() or DEFAULT_LOCALE
    text = (
        CATALOGS.get(loc, {}).get(key)
        or CATALOGS.get("en", {}).get(key)
        or next((c[key] for c in CATALOGS.values() if key in c), None)
        or key
    )
    if params:
        try:
            return text.format(**params)
        except (KeyError, ValueError):
            return text
    return text


def msg(key: str, **params: Any) -> str:
    """Translate for the current request locale (X-Lang)."""
    return t(key, None, **params)


def localize(text: str, locale: Locale | None = None, **params: Any) -> str:
    """If text is a message key, translate it; otherwise return as-is."""
    from app.i18n.locale import get_locale

    loc = locale or get_locale()
    if text in MESSAGE_KEYS:
        return t(text, loc, **params)
    return text
