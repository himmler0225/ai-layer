"""Bắt lỗi OpenAI — log request_id, message tiếng Việt cho UI."""

from __future__ import annotations

import logging
from typing import Optional

from openai import APIError, APIStatusError, APITimeoutError, RateLimitError


def request_id(exc: Exception) -> Optional[str]:
    rid = getattr(exc, "request_id", None)
    if rid:
        return str(rid)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("request_id"):
            return str(err["request_id"])
    return None


def user_message(exc: Exception) -> str:
    """Text ngắn hiện trong chat khi OpenAI fail."""
    rid = request_id(exc)
    tag = f" Mã lỗi: {rid}." if rid else ""

    if isinstance(exc, RateLimitError):
        return f"OpenAI đang chặn rate limit — đợi vài giây rồi thử lại.{tag}"
    if isinstance(exc, APITimeoutError):
        return f"OpenAI phản hồi quá lâu. Thử gửi lại.{tag}"
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", 0)
        if code == 401:
            return "OPENAI_API_KEY sai hoặc hết hạn — kiểm tra .env / Supabase config."
        if code >= 500:
            return f"OpenAI đang lỗi phía server. Gửi lại tin nhắn.{tag}"
        if code == 400:
            return (
                f"OpenAI không xử lý được request (thường do prompt/tool quá nặng). "
                f"Thử hỏi ngắn hơn hoặc bỏ bớt lịch sử chat.{tag}"
            )
    if isinstance(exc, APIError):
        raw = str(exc)
        if "error occurred while processing" in raw.lower():
            return f"OpenAI crash giữa chừng — thử lại. Nếu lặp lại, báo dev kèm mã lỗi.{tag}"
        return f"Lỗi OpenAI: {raw[:200]}{tag}"

    return f"Lỗi không xác định: {exc}{tag}"


def should_retry(exc: Exception) -> bool:
    if isinstance(exc, (RateLimitError, APITimeoutError)):
        return True
    if isinstance(exc, APIStatusError) and getattr(exc, "status_code", 0) in (
        500,
        502,
        503,
        504,
    ):
        return True
    return False


def log_error(logger: logging.Logger, exc: Exception, *, where: str = "") -> None:
    logger.error(
        "[openai] %s err=%s request_id=%s", where or "call", exc, request_id(exc)
    )
