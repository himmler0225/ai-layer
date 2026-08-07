WEB_TOOLS = [
    {
        "type": "function",
        "name": "web_search",
        "description": "Tìm kiếm thông tin trên web/Google (qua Tavily). DÙNG KHI: câu hỏi cần thông tin ngoài phạm vi Youtube/Tiktok/phim, hoặc cần nguồn web bên ngoài để xác minh/tổng hợp.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa/câu hỏi tìm kiếm"},
                "max_results": {"type": "integer", "default": 5, "maximum": 10},
            },
            "required": ["query"],
        },
    },
]
