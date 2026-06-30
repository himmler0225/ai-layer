from __future__ import annotations

from app.clients import movie_api

_PROVIDER_PARAM = {
    "type": "string",
    "enum": ["kkphim", "ophim"],
    "default": "kkphim",
    "description": "Nguồn phim: kkphim (phimapi.com) hoặc ophim (ophim1.com). Mặc định kkphim.",
}

_PAGE_PARAM = {"type": "integer", "default": 1, "minimum": 1}
_LIMIT_PARAM = {"type": "integer", "default": 10, "minimum": 1, "maximum": 24}

_LIST_FILTER_PROPS = {
    "category": {"type": "string", "description": "Slug thể loại lọc, vd hanh-dong"},
    "country": {"type": "string", "description": "Slug quốc gia lọc, vd han-quoc"},
    "year": {"type": "integer", "description": "Năm phát hành, vd 2024"},
    "sort_lang": {
        "type": "string",
        "enum": ["vietsub", "thuyet-minh", "long-tieng"],
        "description": "Lọc theo ngôn ngữ phụ đề",
    },
    "sort_field": {
        "type": "string",
        "enum": ["modified.time", "_id", "year"],
        "description": "Trường sắp xếp",
    },
    "sort_type": {"type": "string", "enum": ["desc", "asc"], "description": "Chiều sắp xếp"},
}

MOVIE_TOOLS = [
    {
        "type": "function",
        "name": "movie_search",
        "description": (
            "Tìm phim theo từ khóa. kkphim: chỉ tên phim; ophim: tên phim + diễn viên. "
            "DÙNG KHI user hỏi tên phim, diễn viên, hoặc muốn tìm phim cụ thể. "
            "TRẢ VỀ danh sách phim kèm slug — dùng movie_get_detail để lấy chi tiết."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Từ khóa tìm kiếm"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
            },
            "required": ["keyword"],
        },
    },
    {
        "type": "function",
        "name": "movie_get_detail",
        "description": (
            "Lấy chi tiết phim: mô tả, thể loại, quốc gia, tập phim, link xem. "
            "YÊU CẦU slug từ movie_search hoặc danh sách phim."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug phim, vd avatar-2"},
                "provider": _PROVIDER_PARAM,
            },
            "required": ["slug"],
        },
    },
    {
        "type": "function",
        "name": "movie_list_new",
        "description": "Lấy danh sách phim mới cập nhật. DÙNG KHI user hỏi phim mới, phim vừa ra.",
        "parameters": {
            "type": "object",
            "properties": {
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
            },
        },
    },
    {
        "type": "function",
        "name": "movie_list_by_type",
        "description": (
            "Lấy danh sách phim theo loại. "
            "type: phim-bo | phim-le | tv-shows | hoat-hinh | phim-vietsub | phim-thuyet-minh | phim-long-tieng. "
            "kkphim hỗ trợ filter nâng cao; ophim chỉ page + limit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": list(movie_api.MOVIE_LIST_TYPES),
                    "description": "Loại phim",
                },
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["type"],
        },
    },
    {
        "type": "function",
        "name": "movie_list_by_genre",
        "description": "Lấy phim theo thể loại (slug). DÙNG KHI user hỏi phim hành động, kinh dị, tình cảm…",
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug thể loại, vd hanh-dong"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["slug"],
        },
    },
    {
        "type": "function",
        "name": "movie_list_by_country",
        "description": "Lấy phim theo quốc gia (slug). DÙNG KHI user hỏi phim Hàn, Mỹ, Trung…",
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug quốc gia, vd han-quoc"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["slug"],
        },
    },
    {
        "type": "function",
        "name": "movie_list_by_year",
        "description": "Lấy phim theo năm phát hành. DÙNG KHI user hỏi phim năm 2024, 2023…",
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Năm 4 chữ số, vd 2024"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["year"],
        },
    },
    {
        "type": "function",
        "name": "movie_get_metadata",
        "description": (
            "Lấy metadata thể loại hoặc quốc gia (slug dùng cho filter/list). "
            "kind: genres | countries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["genres", "countries"]},
                "provider": _PROVIDER_PARAM,
            },
            "required": ["kind"],
        },
    },
]
