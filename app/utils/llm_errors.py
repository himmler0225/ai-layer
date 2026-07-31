import json
import logging

from openai import APIError, APIStatusError, APITimeoutError, RateLimitError

from app.i18n import t


def request_id(exc: Exception) -> str | None:
    """Request id.

    Args:
        exc: (Exception) Tham số `exc`.

    Returns:
        (str | None) Kết quả trả về."""
    rid = getattr(exc, "request_id", None)
    if rid:
        return str(rid)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("request_id"):
            return str(err["request_id"])
    return None


def user_message(exc: Exception) -> tuple[str, str]:
    """User message.

    Args:
        exc: (Exception) Tham số `exc`.

    Returns:
        (tuple[str, str]) Kết quả trả về."""
    rid = request_id(exc)
    tag_vi = f" Mã lỗi: {rid}." if rid else ""
    tag_en = f" Error code: {rid}." if rid else ""
    tag = {"tag": tag_vi}
    tag_en_kw = {"tag": tag_en}

    if isinstance(exc, RateLimitError):
        return t("llm.rate_limit", "vi", **tag), t("llm.rate_limit", "en", **tag_en_kw)
    if isinstance(exc, APITimeoutError):
        return t("llm.timeout", "vi", **tag), t("llm.timeout", "en", **tag_en_kw)
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", 0)
        raw = str(exc)
        if code == 401:
            return t("llm.invalid_key", "vi"), t("llm.invalid_key", "en")
        if code == 402 or "quota" in raw.lower() or "billing" in raw.lower():
            return t("llm.quota", "vi", **tag), t("llm.quota", "en", **tag_en_kw)
        if code in (502, 503, 504):
            kw = {"code": code, "tag": tag_vi}
            kw_en = {"code": code, "tag": tag_en}
            return t("llm.gateway", "vi", **kw), t("llm.gateway", "en", **kw_en)
        if code >= 500:
            kw = {"code": code, "tag": tag_vi}
            kw_en = {"code": code, "tag": tag_en}
            return t("llm.server", "vi", **kw), t("llm.server", "en", **kw_en)
        if code == 400:
            if "upstream" in raw.lower() or "từ chối" in raw.lower():
                return (
                    t("llm.bad_request_upstream", "vi", **tag),
                    t("llm.bad_request_upstream", "en", **tag_en_kw),
                )
            return t("llm.bad_request", "vi", **tag), t("llm.bad_request", "en", **tag_en_kw)
    if isinstance(exc, APIError):
        raw = str(exc)
        if "quota" in raw.lower() or "billing" in raw.lower():
            return t("llm.quota", "vi", **tag), t("llm.quota", "en", **tag_en_kw)
        if "error occurred while processing" in raw.lower():
            return t("llm.crash", "vi", **tag), t("llm.crash", "en", **tag_en_kw)
        detail = raw[:200]
        return (
            t("llm.raw", "vi", detail=detail, tag=tag_vi),
            t("llm.raw", "en", detail=detail, tag=tag_en),
        )
    detail = str(exc)
    return (
        t("llm.unknown", "vi", detail=detail, tag=tag_vi),
        t("llm.unknown", "en", detail=detail, tag=tag_en),
    )


def _is_connection_drop(exc: Exception) -> bool:
    """SSE/body rỗng, TCP reset, gateway đóng giữa chừng."""
    if isinstance(exc, (ConnectionError, TimeoutError, json.JSONDecodeError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (54, 104, 110, 111):
        # ECONNRESET, ECONNREFUSED, ETIMEDOUT, ECONNREFUSED (platform-dependent)
        return True
    msg = str(exc).lower()
    needles = (
        "connection reset",
        "connection aborted",
        "connection closed",
        "broken pipe",
        "expecting value",
        "incomplete read",
        "disconnected",
        "remote end closed",
    )
    return any(n in msg for n in needles)


def should_retry(exc: Exception) -> bool:
    """Should retry.

    Args:
        exc: (Exception) Tham số `exc`.

    Returns:
        (bool) Kết quả trả về."""
    if isinstance(exc, (RateLimitError, APITimeoutError)):
        return True
    if isinstance(exc, APIStatusError) and getattr(exc, "status_code", 0) in (
        500,
        502,
        503,
        504,
    ):
        return True
    if _is_connection_drop(exc):
        return True
    return False


def is_upstream_gateway_error(exc: Exception) -> bool:
    """Is upstream gateway error.

    Args:
        exc: (Exception) Tham số `exc`.

    Returns:
        (bool) Kết quả trả về."""
    return isinstance(exc, APIStatusError) and getattr(exc, "status_code", 0) in (
        502,
        503,
        504,
    )


def log_error(logger: logging.Logger, exc: Exception, *, where: str = "") -> None:
    """Log error.

    Args:
        logger: (logging.Logger) Tham số `logger`.
        exc: (Exception) Tham số `exc`.
        where: (str, mặc định '') Tham số `where`.

    Returns:
        (None) Kết quả trả về."""
    logger.error(
        "[llm] %s err=%s request_id=%s",
        where or "call",
        exc,
        request_id(exc),
    )
