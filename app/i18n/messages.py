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
    # --- Agent status (SSE `status` events) ---
    "agent.status.analyzing": {
        "vi": "Đang phân tích câu hỏi…",
        "en": "Analyzing your question…",
    },
    "agent.status.calling_tools": {
        "vi": "Đang gọi tool dữ liệu…",
        "en": "Calling data tools…",
    },
    "agent.status.synthesizing": {
        "vi": "Đang tổng hợp câu trả lời từ dữ liệu đã thu…",
        "en": "Summarizing answer from collected data…",
    },
    "agent.status.writing": {
        "vi": "Đang viết câu trả lời từ dữ liệu đã thu…",
        "en": "Writing answer from collected data…",
    },
    # --- Agent tool status (SSE `tool_start` events, app/services/agent/events/tool_status.py) ---
    "agent.tool.youtube_search": {"vi": "Đang tìm video YouTube: «{q}»…", "en": 'Searching YouTube for "{q}"…'},
    "agent.tool.youtube_search.generic": {"vi": "Đang tìm video trên YouTube…", "en": "Searching YouTube…"},
    "agent.tool.youtube_get_comments": {"vi": "Đang lấy bình luận video {vid}…", "en": "Fetching comments for {vid}…"},
    "agent.tool.youtube_get_comments.generic": {"vi": "Đang lấy bình luận YouTube…", "en": "Fetching YouTube comments…"},
    "agent.tool.youtube_get_comments_batch.one": {
        "vi": "Đang lấy bình luận video {id}…",
        "en": "Fetching comments for {id}…",
    },
    "agent.tool.youtube_get_comments_batch.many": {
        "vi": "Đang lấy bình luận {n} video YouTube ({id}…)…",
        "en": "Fetching comments from {n} YouTube videos…",
    },
    "agent.tool.youtube_get_comments_batch.generic": {
        "vi": "Đang lấy bình luận nhiều video YouTube…",
        "en": "Fetching YouTube comments (batch)…",
    },
    "agent.tool.youtube_get_transcript": {
        "vi": "Đang lấy transcript video {vid}…",
        "en": "Fetching transcript for {vid}…",
    },
    "agent.tool.youtube_get_transcript.generic": {
        "vi": "Đang lấy transcript YouTube…",
        "en": "Fetching YouTube transcript…",
    },
    "agent.tool.youtube_get_transcript_batch.one": {
        "vi": "Đang lấy transcript video {id}…",
        "en": "Fetching transcript for {id}…",
    },
    "agent.tool.youtube_get_transcript_batch.many": {
        "vi": "Đang lấy transcript {n} video ({id}…)…",
        "en": "Fetching transcripts for {n} videos…",
    },
    "agent.tool.youtube_get_transcript_batch.generic": {
        "vi": "Đang lấy transcript nhiều video…",
        "en": "Fetching YouTube transcripts…",
    },
    "agent.tool.youtube_get_detail": {"vi": "Đang xem chi tiết video {vid}…", "en": "Loading video details {vid}…"},
    "agent.tool.youtube_get_detail.generic": {"vi": "Đang xem chi tiết video…", "en": "Loading video details…"},
    "agent.tool.youtube_get_by_topic": {
        "vi": "Đang lấy video chủ đề {topic}…",
        "en": "Browsing YouTube topic {topic}…",
    },
    "agent.tool.youtube_get_by_topic.generic": {"vi": "Đang lấy video theo chủ đề…", "en": "Browsing by topic…"},
    "agent.tool.youtube_get_by_region": {"vi": "Đang tìm video {gl}: «{q}»…", "en": "Searching {gl}: {q}…"},
    "agent.tool.youtube_get_by_region.generic": {
        "vi": "Đang tìm video khu vực {gl}…",
        "en": "Searching region {gl}…",
    },
    "agent.tool.youtube_get_channel_info": {"vi": "Đang xem kênh {ch}…", "en": "Loading channel {ch}…"},
    "agent.tool.youtube_get_channel_info.generic": {"vi": "Đang xem thông tin kênh…", "en": "Loading channel info…"},
    "agent.tool.youtube_get_channel_videos": {
        "vi": "Đang lấy video của kênh {ch}…",
        "en": "Fetching videos from {ch}…",
    },
    "agent.tool.youtube_get_channel_videos.generic": {
        "vi": "Đang lấy video kênh…",
        "en": "Fetching channel videos…",
    },
    "agent.tool.tiktok_search": {"vi": "Đang tìm TikTok: «{q}»…", "en": 'Searching TikTok for "{q}"…'},
    "agent.tool.tiktok_search.generic": {"vi": "Đang tìm video TikTok…", "en": "Searching TikTok…"},
    "agent.tool.tiktok_comments": {
        "vi": "Đang lấy bình luận TikTok ({aweme})…",
        "en": "Fetching TikTok comments ({aweme})…",
    },
    "agent.tool.tiktok_comments.generic": {"vi": "Đang lấy bình luận TikTok…", "en": "Fetching TikTok comments…"},
    "agent.tool.tiktok_transcript": {
        "vi": "Đang lấy transcript TikTok ({aweme})…",
        "en": "Fetching TikTok transcript ({aweme})…",
    },
    "agent.tool.tiktok_transcript.generic": {
        "vi": "Đang lấy transcript TikTok…",
        "en": "Fetching TikTok transcript…",
    },
    "agent.tool.tiktok_video_info.no_url": {"vi": "Đang xem video TikTok…", "en": "Loading TikTok video…"},
    "agent.tool.tiktok_video_info.with_url": {"vi": "Đang xem thông tin video TikTok…", "en": "Loading TikTok video…"},
    "agent.tool.tiktok_profile": {"vi": "Đang xem profile @{handle}…", "en": "Loading @{handle}…"},
    "agent.tool.tiktok_profile.generic": {"vi": "Đang xem profile TikTok…", "en": "Loading TikTok profile…"},
    "agent.tool.search_movie_summary": {
        "vi": "Đang đọc tổng quan review «{pid}»…",
        "en": "Reading saved summary for {pid}…",
    },
    "agent.tool.search_movie_summary.generic": {
        "vi": "Đang đọc tổng quan review…",
        "en": "Reading movie summary…",
    },
    "agent.tool.search_aspect_evidence": {
        "vi": "Đang tìm chi tiết {aspect} — {pid}…",
        "en": "Searching {aspect} evidence for {pid}…",
    },
    "agent.tool.search_aspect_evidence.generic": {
        "vi": "Đang tìm chi tiết review…",
        "en": "Searching review details…",
    },
    "agent.tool.get_raw_reviews": {"vi": "Đang lấy review gốc «{pid}»…", "en": "Fetching raw reviews for {pid}…"},
    "agent.tool.get_raw_reviews.generic": {"vi": "Đang lấy review gốc…", "en": "Fetching raw reviews…"},
    "agent.tool.extract_id_from_url": {"vi": "Đang phân tích link video…", "en": "Parsing video URL…"},
    "agent.tool.default": {"vi": "Đang chạy {tool}…", "en": "Running {tool}…"},
}


def t(key: str, locale: Locale, **params: Any) -> str:
    """T.

    Args:
        key: (str) Tham số `key`.
        locale: (Locale) Tham số `locale`.
        **params: (Any) Tham số `**params`.

    Returns:
        (str) Kết quả trả về."""
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(locale) or entry.get("en") or key
    if params:
        return text.format(**params)
    return text


def both(key: str, **params: Any) -> tuple[str, str]:
    """Lấy đồng thời (vi, en) từ MESSAGES — dùng cho payload SSE gửi cả 2 ngôn ngữ cùng lúc."""
    return t(key, "vi", **params), t(key, "en", **params)


def pick(vi: str, en: str, locale: Locale) -> str:
    """Pick.

    Args:
        vi: (str) Tham số `vi`.
        en: (str) Tham số `en`.
        locale: (Locale) Tham số `locale`.

    Returns:
        (str) Kết quả trả về."""
    return vi if locale == "vi" else en


def localize(text: str, locale: Locale, **params: Any) -> str:
    """Localize.

    Args:
        text: (str) Tham số `text`.
        locale: (Locale) Tham số `locale`.
        **params: (Any) Tham số `**params`.

    Returns:
        (str) Kết quả trả về."""
    if text in MESSAGES:
        return t(text, locale, **params)
    return text
