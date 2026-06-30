RAG_TOOLS = [
    {
        'type': 'function',
        'name': 'search_movie_summary',
        'description': 'L1 — tổng quan review phim đã ingest theo aspect. Gọi TRƯỚC khi crawl. movie_id = slug (vd. dune-part-two). Trả coverage: sufficient|partial|none.',
        'parameters': {
            'type': 'object',
            'properties': {
                'movie_id': {'type': 'string', 'description': 'Slug phim, vd. dune-part-two'},
                'query': {'type': 'string', 'description': 'Câu hỏi người dùng'},
                'aspect': {'type': 'string', 'description': 'plot|acting|visuals|pacing|sound|ending|themes|comparison|other'},
            },
            'required': ['movie_id', 'query'],
        },
    },
    {
        'type': 'function',
        'name': 'search_aspect_evidence',
        'description': 'L2 — snippet review chi tiết khi L1 partial. Dùng cùng movie_id + query; có thể chỉ định aspect.',
        'parameters': {
            'type': 'object',
            'properties': {
                'movie_id': {'type': 'string'},
                'query': {'type': 'string'},
                'aspect': {'type': 'string'},
            },
            'required': ['movie_id', 'query'],
        },
    },
    {
        'type': 'function',
        'name': 'get_raw_reviews',
        'description': 'L3 — review gốc top likes (nguyên văn) khi cần bằng chứng.',
        'parameters': {
            'type': 'object',
            'properties': {
                'movie_id': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 10},
            },
            'required': ['movie_id'],
        },
    },
]
