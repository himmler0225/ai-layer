"""Map exceptions and message keys to localized client text."""

from app.exceptions import AiLayerError
from app.i18n import get_locale, localize, t


def client_message(exc: AiLayerError, locale: str | None = None) -> str:
    """Client message.

    Args:
        exc: (AiLayerError) Tham số `exc`.
        locale: (str | None, mặc định None) Tham số `locale`.

    Returns:
        (str) Kết quả trả về."""
    loc = locale or get_locale()
    if exc.message_key:
        return t(exc.message_key, loc, **exc.message_params)
    if exc.message_en and loc == "en":
        return exc.message_en
    return localize(exc.message, loc, **exc.message_params)


def localize_detail(detail: str, locale: str | None = None) -> str:
    """Localize detail.

    Args:
        detail: (str) Tham số `detail`.
        locale: (str | None, mặc định None) Tham số `locale`.

    Returns:
        (str) Kết quả trả về."""
    return localize(str(detail), locale or get_locale())
