import json
import logging

from openai import APIError, APIStatusError, APITimeoutError, RateLimitError

from app.config.logger import log_event
from app.i18n import get_locale, t


def request_id(exc: Exception) -> str | None:
    """Extract the upstream request ID from an OpenAI SDK exception, if present.

    Checks the exception's `request_id` attribute first, then falls back
    to the `error.request_id` field of its response body.

    Args:
        exc: The exception raised by the OpenAI client.

    Returns:
        The request ID as a string, or None if not found.
    """
    rid = getattr(exc, "request_id", None)
    if rid:
        return str(rid)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("request_id"):
            return str(err["request_id"])
    return None


def _error_tag(rid: str | None, locale: str) -> str:
    if not rid:
        return ""
    if locale == "vi":
        return f" Mã lỗi: {rid}."
    return f" Error code: {rid}."


def user_message(exc: Exception, locale: str | None = None) -> str:
    """Localized user-facing message for an LLM/upstream exception."""
    loc = locale or get_locale()
    rid = request_id(exc)
    tag = {"tag": _error_tag(rid, loc)}

    if isinstance(exc, RateLimitError):
        return t("llm.rate_limit", loc, **tag)
    if isinstance(exc, APITimeoutError):
        return t("llm.timeout", loc, **tag)
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", 0)
        raw = str(exc)
        if code == 401:
            return t("llm.invalid_key", loc)
        if code == 402 or "quota" in raw.lower() or "billing" in raw.lower():
            return t("llm.quota", loc, **tag)
        if code in (502, 503, 504):
            return t("llm.gateway", loc, code=code, **tag)
        if code >= 500:
            return t("llm.server", loc, code=code, **tag)
        if code == 400:
            if "upstream" in raw.lower() or "từ chối" in raw.lower():
                return t("llm.bad_request_upstream", loc, **tag)
            return t("llm.bad_request", loc, **tag)
    if isinstance(exc, APIError):
        raw = str(exc)
        if "quota" in raw.lower() or "billing" in raw.lower():
            return t("llm.quota", loc, **tag)
        if "error occurred while processing" in raw.lower():
            return t("llm.crash", loc, **tag)
        return t("llm.raw", loc, detail=raw[:200], **tag)
    return t("llm.unknown", loc, detail=str(exc), **tag)


def _is_connection_drop(exc: Exception) -> bool:
    """Detect a mid-request connection drop: empty SSE/body, TCP reset, or gateway closing early."""
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
    """Decide whether an LLM/upstream call should be retried after this exception.

    Args:
        exc: The exception raised by the LLM call.

    Returns:
        True for rate limits, timeouts, 5xx status errors, or detected
        connection drops; False otherwise.
    """
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
    """Check whether an exception represents a 502/503/504 gateway error from the upstream API.

    Args:
        exc: The exception raised by the LLM call.

    Returns:
        True if `exc` is an `APIStatusError` with status code 502, 503, or 504.
    """
    return isinstance(exc, APIStatusError) and getattr(exc, "status_code", 0) in (
        502,
        503,
        504,
    )


def log_error(logger: logging.Logger, exc: Exception, *, where: str = "") -> None:
    """Log an LLM/upstream exception with a consistent format."""
    logger.error(
        log_event(
            "llm",
            "call failed",
            where=where or "call",
            error=exc,
            request_id=request_id(exc),
        )
    )
