TIKTOK_TOOLS = [
    {
        "type": "function",
        "name": "tiktok_search",
        "description": "Tìm kiếm video TikTok theo từ khóa. DÙNG KHI: cần tìm video review, xu hướng, nội dung về sản phẩm/chủ đề trên TikTok. TRẢ VỀ: danh sách video kèm thông tin tác giả, stats, description. KHÔNG DÙNG khi user đã paste link TikTok — gọi tiktok_video_info trực tiếp.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Từ khóa tìm kiếm"},
                "cursor": {"type": "integer", "default": 0},
                "sort_by": {"type": "string", "enum": ["most-liked", "most-viewed", "most-recent", "most-relevant"]},
                "date_posted": {"type": "string", "enum": ["today", "this-week", "this-month", "this-year"]},
                "region": {"type": "string", "description": "Mã quốc gia proxy (US, VN...)"},
            },
            "required": ["keyword"],
        },
    },
    {
        "type": "function",
        "name": "tiktok_video_info",
        "description": "Lấy thông tin chi tiết của một video TikTok: views, likes, comments, description, tác giả. YÊU CẦU: phải có URL đầy đủ của video TikTok.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "TikTok video URL đầy đủ"}},
            "required": ["url"],
        },
    },
    {
        "type": "function",
        "name": "tiktok_comments",
        "description": "Lấy bình luận của người xem cho một video TikTok. YÊU CẦU: aweme_id (video ID số, lấy từ tiktok_search hoặc tiktok_video_info). DÙNG KHI: cần ý kiến thực tế từ người dùng về sản phẩm/chủ đề trong video.",
        "parameters": {
            "type": "object",
            "properties": {
                "aweme_id": {"type": "string", "description": "TikTok video ID (số)"},
                "cursor": {"type": "integer", "default": 0},
                "count": {"type": "integer", "default": 20, "maximum": 50},
            },
            "required": ["aweme_id"],
        },
    },
    {
        "type": "function",
        "name": "tiktok_profile",
        "description": "Lấy thông tin profile TikTok: follower count, following, bio, số video. DÙNG KHI: user muốn nghiên cứu một creator/influencer cụ thể. YÊU CẦU: handle (không cần @).",
        "parameters": {
            "type": "object",
            "properties": {"handle": {"type": "string", "description": "TikTok handle (không cần @)"}},
            "required": ["handle"],
        },
    },
    {
        "type": "function",
        "name": "tiktok_transcript",
        "description": "Lấy transcript (phụ đề/lời thoại) của một video TikTok qua TikHub. DÙNG KHI: cần phân tích nội dung creator nói trong video, kết hợp với tiktok_comments. YÊU CẦU: aweme_id (video ID số). TRẢ VỀ: text, language, available (False nếu video không có caption).",
        "parameters": {
            "type": "object",
            "properties": {"aweme_id": {"type": "string", "description": "TikTok video ID (số)"}},
            "required": ["aweme_id"],
        },
    },
]
