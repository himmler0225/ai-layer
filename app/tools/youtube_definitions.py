YOUTUBE_TOOLS = [
    {
        "type": "function",
        "name": "youtube_search",
        "description": "Tìm video YouTube theo từ khóa. DÙNG max_results=5, chọn đúng 3 video view cao nhất rồi gọi comments_batch + transcript_batch. KHÔNG gọi search lại. KHÔNG liệt kê video trong câu trả lời.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Từ khóa tìm kiếm"},
                "max_results": {"type": "integer", "default": 5, "maximum": 5},
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
        "type": "function",
        "name": "youtube_get_by_topic",
        "description": "Lấy video theo chủ đề từ kênh YouTube chính thức. DÙNG KHI: user muốn xem video theo thể loại cụ thể. CHỦ ĐỀ HỖ TRỢ: music, gaming, news, sports, tech, beauty, food, travel.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["music", "gaming", "news", "sports", "tech", "beauty", "food", "travel"],
                },
                "max_results": {"type": "integer", "default": 20, "maximum": 50},
            },
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_shorts",
        "description": "Lấy danh sách YouTube Shorts đang thịnh hành. DÙNG KHI: user hỏi về Shorts hoặc video ngắn.",
        "parameters": {
            "type": "object",
            "properties": {"max_results": {"type": "integer", "default": 20, "maximum": 50}},
        },
    },
    {
        "type": "function",
        "name": "youtube_get_live",
        "description": "Lấy danh sách video đang live stream trên YouTube. DÙNG KHI: user hỏi về livestream đang diễn ra. Có thể lọc theo từ khóa tùy chọn.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa lọc (tùy chọn)", "default": ""},
                "max_results": {"type": "integer", "default": 20, "maximum": 50},
            },
        },
    },
    {
        "type": "function",
        "name": "youtube_get_by_region",
        "description": "Lấy video phổ biến theo khu vực địa lý cụ thể. DÙNG KHI: user muốn xem nội dung từ một quốc gia cụ thể. VÍ DỤ: gl=VN hl=vi query=Hà Nội để lấy video về Hà Nội.",
        "parameters": {
            "type": "object",
            "properties": {
                "gl": {"type": "string", "description": "Mã quốc gia (VN, JP, US...)"},
                "hl": {"type": "string", "description": "Mã ngôn ngữ (vi, ja, en...)", "default": "vi"},
                "query": {"type": "string", "description": "Từ khóa tìm kiếm theo ngôn ngữ địa phương"},
                "max_results": {"type": "integer", "default": 20, "maximum": 100},
            },
            "required": ["gl", "query"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_detail",
        "description": "Lấy thông tin chi tiết video: title, channel, views, description, thời lượng. YÊU CẦU: phải có video_id trước — gọi youtube_search nếu chưa có.",
        "parameters": {
            "type": "object",
            "properties": {"video_id": {"type": "string", "description": "YouTube video ID (vd: dQw4w9WgXcQ)"}},
            "required": ["video_id"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_comments",
        "description": "Lấy bình luận cho MỘT video YouTube. YÊU CẦU: phải có video_id. ƯU TIÊN dùng youtube_get_comments_batch khi muốn phân tích nhận xét — tool đơn lẻ này dễ bị rỗng nếu video đó khoá comment.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string"},
                "max_comments": {"type": "integer", "default": 20, "maximum": 20},
                "sort": {"type": "string", "enum": ["newest", "top"], "default": "newest"},
            },
            "required": ["video_id"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_comments_batch",
        "description": "Lấy bình luận của NHIỀU video YouTube song song và gộp lại — CÁCH NÊN DÙNG để phân tích nhận xét cộng đồng. YÊU CẦU: mảng video_ids (chọn 3-5 video view CAO NHẤT từ youtube_search). Video bị khoá/0 comment sẽ tự bị bỏ qua, lấy comment từ các video còn lại — tránh được lỗi 'không có nhận xét' khi video top bị tắt comment. TRẢ VỀ: videos_with_comments, videos_skipped, total_comments, results[]. Chỉ cần gọi 1 lần với 3-5 id.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 video_id, ưu tiên view cao nhất",
                },
                "max_per_video": {"type": "integer", "default": 20, "maximum": 30},
                "sort": {"type": "string", "enum": ["top", "newest"], "default": "top"},
            },
            "required": ["video_ids"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_transcript",
        "description": "Lấy transcript (phụ đề/lời thoại) của một video YouTube. DÙNG KHI: cần phân tích nội dung video (reviewer nói gì) thay vì chỉ comment. Kết hợp với youtube_get_comments_batch để có cả nội dung lẫn phản ứng cộng đồng. TRẢ VỀ: text transcript, language, available (False nếu video không có caption). LƯU Ý: ~60-70% video có caption. Nếu available=False, bỏ qua và dùng comment.",
        "parameters": {
            "type": "object",
            "properties": {"video_id": {"type": "string", "description": "YouTube video ID"}},
            "required": ["video_id"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_transcript_batch",
        "description": "Lấy transcript của NHIỀU video YouTube song song — hiệu quả hơn gọi từng cái. DÙNG KHI: muốn phân tích nội dung nhiều video cùng lúc (kết hợp comments + transcript). TRẢ VỀ: dict {video_id: transcript_data}. Video không có caption → null. Tối đa 8 video_ids.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 video_id cần lấy transcript",
                }
            },
            "required": ["video_ids"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_channel_info",
        "description": "Lấy thông tin kênh YouTube: tên, subscriber, mô tả, avatar. YÊU CẦU: phải có channel_id (dạng UC...) hoặc @handle.",
        "parameters": {
            "type": "object",
            "properties": {"channel_id": {"type": "string", "description": "Channel ID (UCxxxx) hoặc @handle"}},
            "required": ["channel_id"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_channel_videos",
        "description": "Lấy danh sách video mới nhất của một kênh YouTube. YÊU CẦU: phải có channel_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "max_results": {"type": "integer", "default": 30, "maximum": 50},
            },
            "required": ["channel_id"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_channel_playlists",
        "description": "Lấy danh sách playlist của một kênh YouTube. YÊU CẦU: phải có channel_id.",
        "parameters": {
            "type": "object",
            "properties": {"channel_id": {"type": "string"}},
            "required": ["channel_id"],
        },
    },
    {
        "type": "function",
        "name": "youtube_get_playlist_videos",
        "description": "Lấy danh sách video trong một playlist YouTube. YÊU CẦU: phải có playlist_id (dạng PL...). Có thể lấy từ youtube_get_channel_playlists.",
        "parameters": {
            "type": "object",
            "properties": {
                "playlist_id": {"type": "string", "description": "Playlist ID (PLxxxx)"},
                "max_results": {"type": "integer", "default": 30, "maximum": 50},
            },
            "required": ["playlist_id"],
        },
    },
]
