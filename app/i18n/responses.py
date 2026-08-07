"""Map exceptions and message keys to localized client text."""

from app.exceptions import AiLayerError
from app.i18n import get_locale, localize, t


def client_message(exc: AiLayerError, locale: str | None = None) -> str:
    loc = locale or get_locale()
    if exc.message_key:
        return t(exc.message_key, loc, **exc.message_params)
    if exc.message_en and loc != "vi":
        # Legacy bilingual fallback when no message_key is set.
        return exc.message_en if loc == "en" else (exc.message_en or exc.message)
    return localize(exc.message, loc, **exc.message_params)


def localize_detail(detail: str, locale: str | None = None) -> str:
    return localize(str(detail), locale or get_locale())
