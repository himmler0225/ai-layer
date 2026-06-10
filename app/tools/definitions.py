YOUTUBE_TOOLS = [
    # ── Tìm kiếm & khám phá ──────────────────────────────────────────────────

    {
        "name": "youtube_search",
        "description": (
            "Tìm kiếm video YouTube theo từ khóa. "
            "DÙNG KHI: cần video_id nhưng user chưa cung cấp link. "
            "TRẢ VỀ: danh sách video gồm video_id, title, view_count. "
            "TIẾP THEO: chọn video view_count cao nhất rồi gọi youtube_get_comments. "
            "KHÔNG DÙNG khi user đã paste link YouTube — gọi extract_id_from_url trước."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword":     {"type": "string", "description": "Từ khóa tìm kiếm"},
                "max_results": {"type": "integer", "default": 5, "maximum": 10},
                "sort": {
                    "type": "string",
                    "enum": ["relevance", "upload_date", "view_count", "rating"],
                    "default": "relevance",
                },
            },
            "required": ["keyword"],
        },
    },

    {
        "name": "youtube_get_by_topic",
        "description": (
            "Lấy video theo chủ đề từ kênh YouTube chính thức. "
            "DÙNG KHI: user muốn xem video theo thể loại cụ thể. "
            "CHỦ ĐỀ HỖ TRỢ: music, gaming, news, sports, tech, beauty, food, travel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic":       {"type": "string", "enum": ["music", "gaming", "news", "sports", "tech", "beauty", "food", "travel"]},
                "max_results": {"type": "integer", "default": 20, "maximum": 50},
            },
            "required": ["topic"],
        },
    },

    {
        "name": "youtube_get_shorts",
        "description": (
            "Lấy danh sách YouTube Shorts đang thịnh hành. "
            "DÙNG KHI: user hỏi về Shorts hoặc video ngắn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 20, "maximum": 50},
            },
        },
    },

    {
        "name": "youtube_get_live",
        "description": (
            "Lấy danh sách video đang live stream trên YouTube. "
            "DÙNG KHI: user hỏi về livestream đang diễn ra. "
            "Có thể lọc theo từ khóa tùy chọn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":       {"type": "string", "description": "Từ khóa lọc (tùy chọn)", "default": ""},
                "max_results": {"type": "integer", "default": 20, "maximum": 50},
            },
        },
    },

    {
        "name": "youtube_get_by_region",
        "description": (
            "Lấy video phổ biến theo khu vực địa lý cụ thể. "
            "DÙNG KHI: user muốn xem nội dung từ một quốc gia cụ thể. "
            "VÍ DỤ: gl=VN hl=vi query=Hà Nội để lấy video về Hà Nội."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gl":          {"type": "string", "description": "Mã quốc gia (VN, JP, US...)"},
                "hl":          {"type": "string", "description": "Mã ngôn ngữ (vi, ja, en...)", "default": "vi"},
                "query":       {"type": "string", "description": "Từ khóa tìm kiếm theo ngôn ngữ địa phương"},
                "max_results": {"type": "integer", "default": 20, "maximum": 100},
            },
            "required": ["gl", "query"],
        },
    },

    # ── Video detail & tương tác ──────────────────────────────────────────────

    {
        "name": "youtube_get_detail",
        "description": (
            "Lấy thông tin chi tiết video: title, channel, views, description, thời lượng. "
            "YÊU CẦU: phải có video_id trước — gọi youtube_search nếu chưa có."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string", "description": "YouTube video ID (vd: dQw4w9WgXcQ)"},
            },
            "required": ["video_id"],
        },
    },

    {
        "name": "youtube_get_comments",
        "description": (
            "Lấy bình luận của người xem cho một video YouTube. "
            "YÊU CẦU: phải có video_id — gọi youtube_search trước nếu chưa có. "
            "Dùng sort='newest' để lấy comment mới nhất. "
            "Chỉ gọi cho TỐI ĐA 1 video mỗi task để tránh tràn token."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "video_id":     {"type": "string"},
                "max_comments": {"type": "integer", "default": 20, "maximum": 20},
                "sort":         {"type": "string", "enum": ["newest", "top"], "default": "newest"},
            },
            "required": ["video_id"],
        },
    },

    # ── Channel ───────────────────────────────────────────────────────────────

    {
        "name": "youtube_get_channel_info",
        "description": (
            "Lấy thông tin kênh YouTube: tên, subscriber, mô tả, avatar. "
            "YÊU CẦU: phải có channel_id (dạng UC...) hoặc @handle."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Channel ID (UCxxxx) hoặc @handle"},
            },
            "required": ["channel_id"],
        },
    },

    {
        "name": "youtube_get_channel_videos",
        "description": (
            "Lấy danh sách video mới nhất của một kênh YouTube. "
            "YÊU CẦU: phải có channel_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id":  {"type": "string"},
                "max_results": {"type": "integer", "default": 30, "maximum": 50},
            },
            "required": ["channel_id"],
        },
    },

    {
        "name": "youtube_get_channel_playlists",
        "description": (
            "Lấy danh sách playlist của một kênh YouTube. "
            "YÊU CẦU: phải có channel_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
            },
            "required": ["channel_id"],
        },
    },

    # ── Playlist ──────────────────────────────────────────────────────────────

    {
        "name": "youtube_get_playlist_videos",
        "description": (
            "Lấy danh sách video trong một playlist YouTube. "
            "YÊU CẦU: phải có playlist_id (dạng PL...). "
            "Có thể lấy từ youtube_get_channel_playlists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "playlist_id": {"type": "string", "description": "Playlist ID (PLxxxx)"},
                "max_results": {"type": "integer", "default": 30, "maximum": 50},
            },
            "required": ["playlist_id"],
        },
    },
]

UTIL_TOOLS = [
    {
        "name": "extract_id_from_url",
        "description": (
            "Trích xuất video_id / URL từ link YouTube hoặc TikTok. Không cần gọi network. "
            "DÙNG KHI: user paste link YouTube hoặc TikTok bất kỳ. "
            "YouTube: trả về video_id — dùng cho youtube_get_detail, youtube_get_comments. "
            "TikTok: trả về url gốc — dùng trực tiếp cho tiktok_video_info, tiktok_comments. "
            "HỖ TRỢ: youtube.com/watch?v=ID, youtu.be/ID, /shorts/ID, tiktok.com/@user/video/ID"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
    },
]

TIKTOK_TOOLS = [
    {
        "name": "tiktok_search",
        "description": (
            "Tìm kiếm video TikTok theo từ khóa. "
            "DÙNG KHI: cần tìm video review, xu hướng, nội dung về sản phẩm/chủ đề trên TikTok. "
            "TRẢ VỀ: danh sách video kèm thông tin tác giả, stats, description. "
            "KHÔNG DÙNG khi user đã paste link TikTok — gọi tiktok_video_info trực tiếp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword":     {"type": "string", "description": "Từ khóa tìm kiếm"},
                "cursor":      {"type": "integer", "default": 0},
                "sort_by":     {"type": "string", "enum": ["most-liked", "most-viewed", "most-recent", "most-relevant"]},
                "date_posted": {"type": "string", "enum": ["today", "this-week", "this-month", "this-year"]},
                "region":      {"type": "string", "description": "Mã quốc gia proxy (US, VN...)"},
            },
            "required": ["keyword"],
        },
    },

    {
        "name": "tiktok_video_info",
        "description": (
            "Lấy thông tin chi tiết của một video TikTok: views, likes, comments, description, tác giả. "
            "YÊU CẦU: phải có URL đầy đủ của video TikTok. "
            "Dùng extract_id_from_url để lấy URL từ link rút gọn nếu cần."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url":            {"type": "string", "description": "TikTok video URL đầy đủ"},
                "get_transcript": {"type": "boolean", "default": False},
                "region":         {"type": "string", "description": "Country code proxy: US, VN..."},
            },
            "required": ["url"],
        },
    },

    {
        "name": "tiktok_comments",
        "description": (
            "Lấy bình luận của người xem cho một video TikTok. "
            "YÊU CẦU: phải có URL đầy đủ của video. "
            "DÙNG KHI: cần ý kiến thực tế từ người dùng về sản phẩm/chủ đề trong video."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url":    {"type": "string", "description": "TikTok video URL đầy đủ"},
                "cursor": {"type": "integer", "default": 0},
            },
            "required": ["url"],
        },
    },

    {
        "name": "tiktok_profile",
        "description": (
            "Lấy thông tin profile TikTok: follower count, following, bio, số video. "
            "DÙNG KHI: user muốn nghiên cứu một creator/influencer cụ thể. "
            "YÊU CẦU: handle (không cần @)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string", "description": "TikTok handle (không cần @)"},
            },
            "required": ["handle"],
        },
    },
]

ALL_TOOLS = YOUTUBE_TOOLS + TIKTOK_TOOLS + UTIL_TOOLS

TOOL_SETS = {
    "youtube": YOUTUBE_TOOLS + UTIL_TOOLS,
    "tiktok":  TIKTOK_TOOLS  + UTIL_TOOLS,
    "all":     ALL_TOOLS,
}
