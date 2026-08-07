"""Locale catalogs — add a module here (e.g. `ja.py`) and register it in CATALOGS."""

from app.i18n.locales import en, vi

CATALOGS: dict[str, dict[str, str]] = {
    "en": en.MESSAGES,
    "vi": vi.MESSAGES,
}

MESSAGE_KEYS: frozenset[str] = frozenset().union(*(catalog.keys() for catalog in CATALOGS.values()))
