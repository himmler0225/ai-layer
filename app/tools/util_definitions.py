UTIL_TOOLS = [
    {
        "type": "function",
        "name": "extract_id_from_url",
        "description": "Trích xuất video_id (YouTube) hoặc URL (TikTok) từ link user dán. DÙNG KHI: user gửi link video thay vì từ khóa — gọi TRƯỚC youtube_get_detail/comments hoặc tiktok_video_info/comments. TRẢ VỀ: platform, video_id hoặc url. Pure local, không cần network.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL video YouTube hoặc TikTok đầy đủ"},
            },
            "required": ["url"],
        },
    },
]
