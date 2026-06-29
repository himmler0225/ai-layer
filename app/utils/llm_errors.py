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
    rid = request_id(exc)
    tag = f" Mã lỗi: {rid}." if rid else ""
    if isinstance(exc, RateLimitError):
        return f"LLM provider đang chặn rate limit — đợi vài giây rồi thử lại.{tag}"
    if isinstance(exc, APITimeoutError):
        return f"LLM provider phản hồi quá lâu. Thử gửi lại.{tag}"
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", 0)
        raw = str(exc)
        if code == 401:
            return "API key LLM sai hoặc hết hạn — kiểm tra Supabase AI_MODELS / .env."
        if code == 402 or "quota" in raw.lower() or "billing" in raw.lower():
            return (
                f"Hết quota hoặc billing LLM provider — kiểm tra key/plan "
                f"(đặt LLM_DEFAULT_PROVIDER=xah nếu chỉ dùng XAH).{tag}"
            )
        if code in (502, 503, 504):
            return (
                f"LLM gateway/upstream đang lỗi ({code}) — thử lại sau vài phút "
                f"hoặc đổi model nhẹ hơn trên Supabase.{tag}"
            )
        if code >= 500:
            return f"LLM provider lỗi phía server ({code}). Gửi lại tin nhắn.{tag}"
        if code == 400:
            if "upstream" in raw.lower() or "từ chối" in raw.lower():
                return (
                    "Model synthesis từ chối request (context quá dài hoặc model upstream lỗi). "
                    f"Thử hỏi ngắn hơn hoặc giảm số vòng tool.{tag}"
                )
            return (
                f"LLM không xử lý được request (prompt/context quá nặng). "
                f"Thử hỏi ngắn hơn.{tag}"
            )
    if isinstance(exc, APIError):
        raw = str(exc)
        if "quota" in raw.lower() or "billing" in raw.lower():
            return (
                f"Hết quota hoặc billing LLM provider — kiểm tra key/plan "
                f"(đặt LLM_DEFAULT_PROVIDER=xah nếu chỉ dùng XAH).{tag}"
            )
        if "error occurred while processing" in raw.lower():
            return f"LLM crash giữa chừng — thử lại. Nếu lặp lại, báo dev kèm mã lỗi.{tag}"
        return f"Lỗi LLM: {raw[:200]}{tag}"
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


def is_upstream_gateway_error(exc: Exception) -> bool:
    return isinstance(exc, APIStatusError) and getattr(exc, "status_code", 0) in (
        502,
        503,
        504,
    )


def log_error(logger: logging.Logger, exc: Exception, *, where: str = "") -> None:
    logger.error(
        "[llm] %s err=%s request_id=%s",
        where or "call",
        exc,
        request_id(exc),
    )
