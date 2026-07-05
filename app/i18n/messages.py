"""User-facing API messages — vi / en (logs stay Vietnamese on server)."""

from typing import Any

Locale = str

MESSAGES: dict[str, dict[str, str]] = {
    "errors.invalid_api_key": {
        "vi": "API key không hợp lệ",
        "en": "Invalid API key",
    },
    "errors.missing_authorization": {
        "vi": "Thiếu header Authorization",
        "en": "Missing authorization",
    },
    "errors.admin_required": {
        "vi": "Cần quyền admin",
        "en": "Admin access required",
    },
    "errors.session_not_found": {
        "vi": "Không tìm thấy phiên chat",
        "en": "Session not found",
    },
    "errors.invalid_token": {
        "vi": "Token không hợp lệ hoặc đã hết hạn",
        "en": "Invalid or expired token",
    },
    "errors.cannot_extract_user": {
        "vi": "Không lấy được thông tin user từ token",
        "en": "Cannot extract user from token",
    },
    "errors.supabase_auth_not_configured": {
        "vi": "Supabase auth chưa cấu hình",
        "en": "Supabase auth is not configured",
    },
    "errors.no_updates": {
        "vi": "Không có trường nào để cập nhật",
        "en": "No updates",
    },
    "errors.cannot_demote_self": {
        "vi": "Không thể hạ quyền tài khoản của chính bạn",
        "en": "Cannot demote your own admin account",
    },
    "errors.agent_no_tool": {
        "vi": "Agent không gọi tool — thử lại hoặc kiểm tra AGENT_SYSTEM / model tool.",
        "en": "Agent did not call any tools — retry or check AGENT_SYSTEM / tool model.",
    },
    "errors.agent_max_iterations": {
        "vi": "Agent không hoàn tất trong {max_iter} vòng",
        "en": "Agent did not finish within {max_iter} iterations",
    },
    "errors.max_output_tokens": {
        "vi": "Đạt giới hạn max_tokens mà chưa có output — tăng max_tokens trên Supabase AI_MODELS",
        "en": "max_output_tokens reached without output — increase max_tokens in Supabase AI_MODELS",
    },
    "errors.config_agent_system": {
        "vi": "AGENT_SYSTEM chưa cấu hình — thêm key trên Supabase config",
        "en": "AGENT_SYSTEM is not configured — add key in Supabase config",
    },
    "errors.database_init_failed": {
        "vi": "Khởi tạo database thất bại",
        "en": "Database initialization failed",
    },
    "errors.generic": {
        "vi": "Đã xảy ra lỗi — vui lòng thử lại",
        "en": "Something went wrong — please try again",
    },
    "llm.rate_limit": {
        "vi": "LLM provider đang chặn rate limit — đợi vài giây rồi thử lại.{tag}",
        "en": "LLM provider rate limit — wait a few seconds and retry.{tag}",
    },
    "llm.timeout": {
        "vi": "LLM provider phản hồi quá lâu. Thử gửi lại.{tag}",
        "en": "LLM provider timed out. Try again.{tag}",
    },
    "llm.invalid_key": {
        "vi": "API key LLM sai hoặc hết hạn — kiểm tra Supabase AI_MODELS / .env.",
        "en": "Invalid or expired LLM API key — check Supabase AI_MODELS / .env.",
    },
    "llm.quota": {
        "vi": "Hết quota hoặc billing LLM provider — kiểm tra key/plan hoặc bật provider khác trong AI_MODELS.{tag}",
        "en": "LLM quota or billing issue — check key/plan or switch provider in AI_MODELS.{tag}",
    },
    "llm.gateway": {
        "vi": "LLM gateway/upstream đang lỗi ({code}) — thử lại sau vài phút hoặc đổi model nhẹ hơn trên Supabase.{tag}",
        "en": "LLM gateway/upstream error ({code}) — retry later or use a lighter model in Supabase.{tag}",
    },
    "llm.server": {
        "vi": "LLM provider lỗi phía server ({code}). Gửi lại tin nhắn.{tag}",
        "en": "LLM provider server error ({code}). Send your message again.{tag}",
    },
    "llm.bad_request_upstream": {
        "vi": "Model synthesis từ chối request (context quá dài hoặc model upstream lỗi). Thử hỏi ngắn hơn hoặc giảm số vòng tool.{tag}",
        "en": "Synthesis model rejected the request (context too long or upstream error). Try a shorter question or fewer tool rounds.{tag}",
    },
    "llm.bad_request": {
        "vi": "LLM không xử lý được request (prompt/context quá nặng). Thử hỏi ngắn hơn.{tag}",
        "en": "LLM could not process the request (prompt/context too heavy). Try a shorter question.{tag}",
    },
    "llm.crash": {
        "vi": "LLM crash giữa chừng — thử lại. Nếu lặp lại, báo dev kèm mã lỗi.{tag}",
        "en": "LLM failed mid-response — retry. If it persists, contact support with the error code.{tag}",
    },
    "llm.unknown": {
        "vi": "Lỗi không xác định: {detail}{tag}",
        "en": "Unknown error: {detail}{tag}",
    },
    "llm.raw": {
        "vi": "Lỗi LLM: {detail}{tag}",
        "en": "LLM error: {detail}{tag}",
    },
}


def t(key: str, locale: Locale, **params: Any) -> str:
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(locale) or entry.get("en") or key
    if params:
        return text.format(**params)
    return text


def pick(vi: str, en: str, locale: Locale) -> str:
    return vi if locale == "vi" else en


def localize(text: str, locale: Locale, **params: Any) -> str:
    if text in MESSAGES:
        return t(text, locale, **params)
    return text
